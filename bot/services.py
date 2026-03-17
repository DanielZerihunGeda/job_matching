from __future__ import annotations

import asyncio
from pathlib import Path
from tempfile import NamedTemporaryFile

from .repository import find_matching_user_ids, upsert_user_titles
from .runtime import AppContext, CVTask


class CVProcessingService:
    ALLOWED_SUFFIXES = {".pdf", ".doc", ".docx"}

    def __init__(self, context: AppContext, parser_max_bytes: int, max_workers: int) -> None:
        self.context = context
        self.parser_max_bytes = parser_max_bytes
        self.max_workers = max_workers

    async def start(self) -> None:
        if self.context.worker_tasks:
            return
        for worker_id in range(self.max_workers):
            task = asyncio.create_task(self._worker_loop(worker_id))
            self.context.worker_tasks.append(task)

    async def stop(self) -> None:
        for task in self.context.worker_tasks:
            task.cancel()
        if self.context.worker_tasks:
            await asyncio.gather(*self.context.worker_tasks, return_exceptions=True)
        self.context.worker_tasks.clear()

    async def enqueue(self, event) -> bool:
        message_file = event.message.file
        if not message_file or not message_file.size:
            return False
        if message_file.size > self.parser_max_bytes:
            await event.reply("You are allowed to upload a document up to 5 MB only.")
            return False

        suffix = Path(message_file.name or "resume.pdf").suffix or ".pdf"
        if suffix.lower() not in self.ALLOWED_SUFFIXES:
            await event.reply("Only PDF, DOC, and DOCX files are supported.")
            return False
        with NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
            temp_path = Path(temp_file.name)

        download_path = await event.download_media(file=str(temp_path))
        if not download_path:
            temp_path.unlink(missing_ok=True)
            return False

        try:
            self.context.queue.put_nowait(
                CVTask(
                    event=event,
                    file_path=Path(download_path),
                    file_name=message_file.name or temp_path.name,
                )
            )
        except asyncio.QueueFull:
            Path(download_path).unlink(missing_ok=True)
            await event.reply("Too many requests right now. Please try again later.")
            return False
        return True

    async def _worker_loop(self, worker_id: int) -> None:
        while True:
            task = await self.context.queue.get()
            try:
                await self._process(task)
            except Exception:
                self.context.logger.exception("Worker %s failed", worker_id)
            finally:
                task.file_path.unlink(missing_ok=True)
                self.context.queue.task_done()

    async def _process(self, task: CVTask) -> None:
        parsed_text = await self.context.parser_client.parse_document(
            task.file_path,
            task.file_name,
        )
        if not parsed_text:
            await task.event.reply(
                "I could not read that document. Upload a clear PDF or DOC file up to 5 MB."
            )
            return

        titles = await self.context.llm_service.classify_cv(parsed_text)
        if titles is None:
            await task.event.reply("The matching service is temporarily unavailable. Please try again.")
            return
        if not titles:
            await task.event.reply(
                "Sorry, I could not match your resume to a supported job title yet.\n\n"
                "ይቅርታ፣ ከሲቪዎ ጋር የሚመጥን የስራ መደብ ማግኘት አልቻልኩም።"
            )
            return

        user_id = int(task.event.sender_id)
        await upsert_user_titles(self.context.pool, user_id, titles)
        await task.event.reply(
            "**Your resume has been analyzed.**\n\n"
            f"Best matching roles: {' | '.join(titles)}\n\n"
            "We will notify you when matching opportunities are posted."
        )


class JobDispatchService:
    def __init__(self, context: AppContext, max_concurrent_forwards: int = 5) -> None:
        self.context = context
        self.forward_semaphore = asyncio.Semaphore(max_concurrent_forwards)

    async def forward_to_relay(self, event, relay_channel: str) -> None:
        try:
            await self.context.user_client.forward_messages(relay_channel, event.message)
        except Exception:
            self.context.logger.exception("Failed to forward source message to relay")

    async def handle_job_post(self, event, relay_channel: str) -> None:
        job_description = event.message.message or ""
        titles = await self.context.llm_service.classify_job_post(job_description)
        if titles is None:
            self.context.logger.warning("LLM failed while classifying job post")
            await self._delete_relay_message(event, relay_channel)
            return
        if not titles:
            self.context.logger.info("No supported job titles matched for relay message %s", event.message.id)
            await self._delete_relay_message(event, relay_channel)
            return

        user_ids = await find_matching_user_ids(self.context.pool, titles)
        if not user_ids:
            self.context.logger.info("No matching users found for titles=%s", ",".join(titles))
            await self._delete_relay_message(event, relay_channel)
            return

        await asyncio.gather(
            *(self._forward_to_user(user_id, event.message) for user_id in user_ids),
            return_exceptions=True,
        )
        await self._delete_relay_message(event, relay_channel)

    async def _forward_to_user(self, user_id: int, message) -> None:
        async with self.forward_semaphore:
            try:
                await self.context.bot_client.forward_messages(user_id, message)
            except Exception:
                self.context.logger.warning("Failed to send job post to user %s", user_id, exc_info=True)

    async def _delete_relay_message(self, event, relay_channel: str) -> None:
        try:
            await self.context.user_client.delete_messages(relay_channel, [event.message.id])
        except Exception:
            self.context.logger.warning("Failed to delete relay message %s", event.message.id, exc_info=True)
