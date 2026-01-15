"""
Main API router for DataReady.io

Aggregates all API routes and provides the main application router.
"""

from fastapi import APIRouter

from src.api.endpoints import interview, audio, report, metadata

api_router = APIRouter()

# Include all endpoint routers
api_router.include_router(
    interview.router,
    prefix="/interview",
    tags=["Interview"]
)

api_router.include_router(
    audio.router,
    prefix="/audio",
    tags=["Audio"]
)

api_router.include_router(
    report.router,
    prefix="/report",
    tags=["Report"]
)

api_router.include_router(
    metadata.router,
    prefix="/metadata",
    tags=["Metadata"]
)
