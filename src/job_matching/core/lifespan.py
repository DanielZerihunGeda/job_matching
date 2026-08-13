"""Application startup and shutdown lifecycle."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Own shared resources that require startup and shutdown handling."""

    logger.info("Starting %s", app.title)
    await app.state.neo4j.start()
    try:
        yield
    finally:
        await app.state.neo4j.close()
        logger.info("Stopping %s", app.title)
