"""
API layer for DataReady.io

Contains FastAPI routers for:
- Interview management
- Audio processing
- Report generation
- WebSocket real-time communication
"""

from src.api.router import api_router

__all__ = ["api_router"]
