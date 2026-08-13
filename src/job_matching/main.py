"""FastAPI application composition and ASGI entrypoint."""

from fastapi import FastAPI

from job_matching.api.router import api_router
from job_matching.core.config import Settings, get_settings
from job_matching.core.lifespan import lifespan
from job_matching.db import Neo4jConnector


def create_app(
    settings: Settings | None = None,
    *,
    neo4j_connector: Neo4jConnector | None = None,
) -> FastAPI:
    """Create and configure the FastAPI application."""

    resolved_settings = settings or get_settings()
    docs_url = "/docs" if resolved_settings.docs_enabled else None
    openapi_url = "/openapi.json" if resolved_settings.docs_enabled else None

    application = FastAPI(
        title=resolved_settings.name,
        version=resolved_settings.version,
        debug=resolved_settings.debug,
        docs_url=docs_url,
        redoc_url=None,
        openapi_url=openapi_url,
        lifespan=lifespan,
    )
    application.state.settings = resolved_settings
    application.state.neo4j = neo4j_connector or Neo4jConnector(
        resolved_settings.neo4j,
        environment=resolved_settings.environment,
        user_agent=f"job-matching-api/{resolved_settings.version}",
    )
    application.include_router(api_router)

    return application


app = create_app()

__all__ = ["app", "create_app"]
