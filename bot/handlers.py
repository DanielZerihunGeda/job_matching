from __future__ import annotations

import asyncio

from telethon import events

from .runtime import AppContext
from .services import CVProcessingService, JobDispatchService


def register_handlers(
    context: AppContext,
    cv_service: CVProcessingService,
    job_service: JobDispatchService,
    relay_channel: str,
    source_channels: tuple[str, ...],
    verification_chat: str,
    ignored_sender_ids: set[int],
) -> None:
    verification_event = asyncio.Event()
    verification_code: dict[str, str | None] = {"code": None}

    @context.bot_client.on(events.NewMessage(chats=[verification_chat], incoming=True))
    async def catch_verification_code(event) -> None:
        text = (event.message.text or "").strip()
        if not text.isdigit():
            return
        verification_code["code"] = text
        verification_event.set()
        await event.reply("Code received. Completing sign-in.")

    @context.bot_client.on(events.NewMessage)
    async def handle_cv_upload(event) -> None:
        if not event.is_private:
            return

        if (event.message.text or "").strip().isdigit():
            return

        sender_id = int(event.sender_id)
        if sender_id in ignored_sender_ids:
            return

        if context.rate_limiter.is_limited(sender_id):
            await event.reply("Too many requests. Please wait a minute and try again.")
            return

        if not event.media or not event.message.file:
            await event.reply(
                "Upload your CV as PDF or DOC/DOCX, maximum 5 MB.\n\n"
                "እባክዎን ሲቪዎን PDF ወይም DOC/DOCX ፋይል በ5MB ገደብ ይላኩ።"
            )
            return

        await cv_service.enqueue(event)

    @context.user_client.on(events.NewMessage(chats=list(source_channels), incoming=True))
    async def relay_job_posts(event) -> None:
        await job_service.forward_to_relay(event, relay_channel)

    @context.bot_client.on(events.NewMessage(chats=[relay_channel], incoming=True))
    async def dispatch_job_posts(event) -> None:
        await job_service.handle_job_post(event, relay_channel)

    async def wait_for_code(timeout_seconds: int = 300) -> str | None:
        try:
            await asyncio.wait_for(verification_event.wait(), timeout=timeout_seconds)
        except asyncio.TimeoutError:
            return None
        code = verification_code["code"]
        verification_code["code"] = None
        verification_event.clear()
        return code

    context.wait_for_verification_code = wait_for_code
