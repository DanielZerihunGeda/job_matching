"""Top-level API router composition."""

from fastapi import APIRouter

from job_matching.api.v1.router import v1_router

api_router = APIRouter(prefix="/api")
api_router.include_router(v1_router)

__all__ = ["api_router"]
