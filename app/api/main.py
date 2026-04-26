"""FastAPI entrypoint for the CafeTwin MVP."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import config as _config  # noqa: F401  # load .env before Logfire config
from app.logfire_setup import configure_logfire, instrument_fastapi


def create_app() -> FastAPI:
    configure_logfire()

    from app.api.routes import router

    app = FastAPI(title="CafeTwin MVP API")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(router)
    instrument_fastapi(app)
    return app


app = create_app()
