from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from clinguide.api.routes import router
from clinguide.api.streaming import stream_router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # Startup: initialize clients, load indexes, etc.
    yield
    # Shutdown: cleanup


def create_app() -> FastAPI:
    app = FastAPI(
        title="ClinGuide",
        description="Clinical Guidelines RAG Assistant",
        version="0.1.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(router)
    app.include_router(stream_router)
    return app


app = create_app()
