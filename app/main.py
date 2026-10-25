from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.routes.health import router as health_router
from app.api.routes.models import router as models_router
from app.core.config import get_settings
from app.db.session import create_db_engine, create_session_factory


def create_app(*, database_url: str | None = None) -> FastAPI:
    """Create and configure the FastAPI application."""

    settings = get_settings()
    engine = create_db_engine(database_url or settings.database_url)
    session_factory = create_session_factory(engine)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        yield
        engine.dispose()

    application = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="Reproducible evaluation and governance for AI model releases.",
        lifespan=lifespan,
    )
    application.state.session_factory = session_factory
    application.include_router(health_router, prefix=settings.api_prefix)
    application.include_router(models_router, prefix=settings.api_prefix)
    return application


app = create_app()
