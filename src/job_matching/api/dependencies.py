"""Reusable FastAPI dependency aliases."""

from typing import Annotated

from fastapi import Depends, Request

from job_matching.db import Neo4jConnector


def get_neo4j(request: Request) -> Neo4jConnector:
    """Return the application-scoped Neo4j connector."""

    connector = getattr(request.app.state, "neo4j", None)
    if connector is None:
        raise RuntimeError("Neo4j connector is not configured on this application")
    return connector


Neo4jDep = Annotated[Neo4jConnector, Depends(get_neo4j)]

__all__ = ["Neo4jDep", "get_neo4j"]
