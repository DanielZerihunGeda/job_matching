from __future__ import annotations

import logging
from pathlib import Path

import httpx


class ParserClient:
    def __init__(self, client: httpx.AsyncClient, parser_url: str, logger: logging.Logger) -> None:
        self.client = client
        self.parser_url = parser_url
        self.logger = logger

    async def parse_document(self, path: Path, filename: str) -> str | None:
        try:
            with path.open("rb") as file_handle:
                response = await self.client.post(
                    self.parser_url,
                    files={"file": (filename, file_handle, "application/octet-stream")},
                )
        except Exception:
            self.logger.exception("Parser service request failed")
            return None

        if response.status_code != 200:
            self.logger.warning(
                "Parser service error status=%s body=%s",
                response.status_code,
                response.text,
            )
            return None

        try:
            payload = response.json()
        except ValueError:
            self.logger.warning("Parser service returned invalid JSON")
            return None
        text = payload.get("text")
        return text if isinstance(text, str) and text.strip() else None
