from __future__ import annotations

import logging

from openai import APIConnectionError, APIError, AsyncOpenAI, BadRequestError, RateLimitError
from pydantic import BaseModel, Field

from .constants import JOB_TITLES
from .prompts import CV_SYSTEM_PROMPT, JOB_POST_SYSTEM_PROMPT


class TitleResponse(BaseModel):
    job_title: list[str] = Field(default_factory=list)


class LLMService:
    def __init__(self, client: AsyncOpenAI, model: str, logger: logging.Logger) -> None:
        self.client = client
        self.model = model
        self.logger = logger
        self.allowed_titles = set(JOB_TITLES)

    async def classify_cv(self, text: str) -> list[str] | None:
        return await self._classify(CV_SYSTEM_PROMPT, text)

    async def classify_job_post(self, text: str) -> list[str] | None:
        return await self._classify(JOB_POST_SYSTEM_PROMPT, f"Job Description:\n\n{text}")

    async def _classify(self, system_prompt: str, user_prompt: str) -> list[str] | None:
        if not system_prompt or not user_prompt:
            return None

        try:
            response = await self.client.responses.parse(
                model=self.model,
                input=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.2,
                text_format=TitleResponse,
            )
        except RateLimitError as exc:
            self.logger.warning("LLM rate limit hit: %s", exc)
            return None
        except (APIConnectionError, APIError, BadRequestError) as exc:
            self.logger.error("LLM request failed: %s", exc)
            return None
        except Exception:
            self.logger.exception("Unexpected LLM failure")
            return None

        parsed = getattr(response, "output_parsed", None)
        if not parsed:
            return []

        titles = []
        seen = set()
        for title in parsed.job_title:
            normalized = title.strip()
            if normalized in self.allowed_titles and normalized not in seen:
                seen.add(normalized)
                titles.append(normalized)
        return titles
