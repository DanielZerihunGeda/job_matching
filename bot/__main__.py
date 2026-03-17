from __future__ import annotations

import asyncio
from pathlib import Path

import httpx
from openai import AsyncOpenAI
from telethon import TelegramClient
from telethon.sessions import SQLiteSession

from .config import Settings
from .db import create_pool, init_schema
from .handlers import register_handlers
from .llm import LLMService
from .logging_config import configure_logger
from .parser_client import ParserClient
from .rate_limiter import SlidingWindowRateLimiter
from .runtime import AppContext
from .services import CVProcessingService, JobDispatchService


async def run() -> None:
    settings = Settings()
    logger = configure_logger()

    session_dir = Path(settings.session_dir)
    session_dir.mkdir(parents=True, exist_ok=True)

    bot_client = TelegramClient(
        SQLiteSession(str(session_dir / "bot")),
        api_id=settings.tg_api_id,
        api_hash=settings.tg_api_hash,
    )
    user_client = TelegramClient(
        SQLiteSession(str(session_dir / "me")),
        api_id=settings.tg_api_id,
        api_hash=settings.tg_api_hash,
    )

    pool = await create_pool(settings.uri)
    await init_schema(pool)

    http_client = httpx.AsyncClient(timeout=settings.parser_timeout_seconds)
    llm_client = AsyncOpenAI(
        api_key=settings.grok_api_key,
        base_url=settings.llm_base_url,
    )

    context = AppContext(
        logger=logger,
        bot_client=bot_client,
        user_client=user_client,
        pool=pool,
        parser_client=ParserClient(http_client, settings.parser_url, logger),
        llm_service=LLMService(llm_client, settings.llm_model, logger),
        rate_limiter=SlidingWindowRateLimiter(
            settings.max_req_per_window,
            settings.rate_limit_window_seconds,
        ),
        queue=asyncio.Queue(maxsize=settings.max_queue_size),
        ignored_sender_ids={settings.account_id, settings.account_id_o},
    )
    cv_service = CVProcessingService(context, settings.parser_max_bytes, settings.max_workers)
    job_service = JobDispatchService(context)

    register_handlers(
        context=context,
        cv_service=cv_service,
        job_service=job_service,
        relay_channel=settings.relay_channel,
        source_channels=settings.source_channels,
        verification_chat=settings.verification_chat,
        ignored_sender_ids=context.ignored_sender_ids,
    )

    try:
        await bot_client.start(bot_token=settings.tg_bot_token)
        await cv_service.start()

        if not user_client.is_connected():
            await user_client.connect()

        if await user_client.get_me() is None:
            sent_code = await user_client.send_code_request(settings.phone)
            logger.info("Verification code sent. Waiting for code from %s", settings.verification_chat)
            if context.wait_for_verification_code is None:
                raise RuntimeError("Verification handler is not configured")
            code = await context.wait_for_verification_code()
            if not code:
                raise TimeoutError("Timed out waiting for verification code")
            await user_client.sign_in(
                settings.phone,
                code,
                phone_code_hash=sent_code.phone_code_hash,
            )

        logger.info("Bot and user clients started successfully")
        await asyncio.gather(
            bot_client.run_until_disconnected(),
            user_client.run_until_disconnected(),
        )
    finally:
        await cv_service.stop()
        await http_client.aclose()
        await llm_client.close()
        await pool.close()
        await bot_client.disconnect()
        await user_client.disconnect()


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()
