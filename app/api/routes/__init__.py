"""API routes package."""
from app.api.routes.files import router as files_router
from app.api.routes.health import router as health_router

__all__ = ["files_router", "health_router"]
