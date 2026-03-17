from __future__ import annotations

from typing import Any

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from .constants import DEFAULT_SOURCE_CHANNELS


class Settings(BaseSettings):
    tg_api_id: int
    tg_api_hash: str
    tg_bot_token: str
    grok_api_key: str
    uri: str
    account_id: int
    account_id_o: int
    phone: str

    parser_url: str = "http://parser:8081/parse"
    llm_model: str = "openai/gpt-oss-120b"
    llm_base_url: str = "https://api.groq.com/openai/v1"
    parser_timeout_seconds: float = 20.0
    parser_max_bytes: int = 5 * 1024 * 1024
    max_queue_size: int = 100
    max_workers: int = 4
    max_req_per_window: int = 3
    rate_limit_window_seconds: int = 60
    source_channels: tuple[str, ...] = DEFAULT_SOURCE_CHANNELS
    relay_channel: str = "testlenj"
    verification_chat: str = "tggcodd"
    session_dir: str = "."

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @field_validator("source_channels", mode="before")
    @classmethod
    def parse_source_channels(cls, value: Any) -> tuple[str, ...]:
        if isinstance(value, str):
            return tuple(item.strip() for item in value.split(",") if item.strip())
        if isinstance(value, (list, tuple, set)):
            return tuple(str(item).strip() for item in value if str(item).strip())
        return DEFAULT_SOURCE_CHANNELS
