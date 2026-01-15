"""
DataReady.io - AI-Powered Data Engineering Mock Interview Platform

Main application entry point.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from src.config.settings import get_settings
from src.api.router import api_router
from src.api.dependencies import cleanup

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup
    logger.info("Starting DataReady.io...")
    settings = get_settings()
    logger.info(f"Running in {'debug' if settings.debug else 'production'} mode")
    
    yield
    
    # Shutdown
    logger.info("Shutting down DataReady.io...")
    await cleanup()


# Create FastAPI application
settings = get_settings()

app = FastAPI(
    title="DataReady.io",
    description="AI-Powered Data Engineering Mock Interview Platform",
    version=settings.app_version,
    lifespan=lifespan,
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins + ["*"],  # Allow all for development
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount API routes
app.include_router(api_router, prefix="/api")

# Mount static files for frontend
app.mount("/static", StaticFiles(directory="static"), name="static")


# ============================================================================
# ROOT ROUTES
# ============================================================================

@app.get("/")
async def root():
    """Serve the main application page."""
    return FileResponse("static/index.html")


@app.get("/interview/{session_id}")
async def interview_page(session_id: str):
    """Serve the interview room page."""
    return FileResponse("static/interview.html")


@app.get("/report/{session_id}")
async def report_page(session_id: str):
    """Serve the report page."""
    return FileResponse("static/report.html")


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "version": settings.app_version,
    }


# ============================================================================
# RUN SERVER
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
    )
