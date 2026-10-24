from fastapi import FastAPI

from app.api.routes.health import router as health_router
from app.core.config import get_settings


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""

    settings = get_settings()
    application = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="Reproducible evaluation and governance for AI model releases.",
    )
    application.include_router(health_router, prefix=settings.api_prefix)
    return application


app = create_app()
