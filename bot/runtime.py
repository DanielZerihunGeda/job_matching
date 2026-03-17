from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Awaitable, Callable

import asyncpg
from telethon import TelegramClient

from .llm import LLMService
from .parser_client import ParserClient
from .rate_limiter import SlidingWindowRateLimiter


@dataclass
class CVTask:
    event: object
    file_path: Path
    file_name: str


@dataclass
class AppContext:
    logger: logging.Logger
    bot_client: TelegramClient
    user_client: TelegramClient
    pool: asyncpg.Pool
    parser_client: ParserClient
    llm_service: LLMService
    rate_limiter: SlidingWindowRateLimiter
    queue: asyncio.Queue[CVTask]
    worker_tasks: list[asyncio.Task] = field(default_factory=list)
    ignored_sender_ids: set[int] = field(default_factory=set)
    wait_for_verification_code: Callable[[], Awaitable[str | None]] | None = None
