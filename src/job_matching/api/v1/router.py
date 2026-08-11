"""Version 1 route composition."""

from fastapi import APIRouter

v1_router = APIRouter(prefix="/v1")

__all__ = ["v1_router"]
