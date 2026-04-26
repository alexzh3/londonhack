"""FastAPI entrypoint for the CafeTwin MVP."""

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app import config as _config
from app.logfire_setup import configure_logfire, instrument_fastapi

logger = logging.getLogger(__name__)


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
    # Static asset mounts so the frontend can load real CCTV video + frames
    # straight from the API server (no separate static origin needed). Tier
    # 1D — real video panel + future before/after image diffs. StaticFiles
    # supports HTTP Range requests so video scrubbing works in the browser.
    cafe_videos_dir = _config.ROOT_DIR / "cafe_videos"
    if cafe_videos_dir.is_dir():
        app.mount(
            "/cafe_videos",
            StaticFiles(directory=cafe_videos_dir),
            name="cafe_videos",
        )
    if _config.DEMO_DATA_DIR.is_dir():
        app.mount(
            "/demo_data",
            StaticFiles(directory=_config.DEMO_DATA_DIR),
            name="demo_data",
        )
    instrument_fastapi(app)

    # Tier 1E: register PatternAgent + OptimizationAgent in MuBit Managed
    # so the Console shows named agents with versioned system prompts.
    # Gated by `CAFETWIN_MUBIT_AGENTS=1`; falls back silently otherwise.
    @app.on_event("startup")
    async def _bootstrap_mubit_agents() -> None:
        from app.mubit_agents import bootstrap_mubit_agents, default_specs, is_enabled

        if not is_enabled():
            return
        try:
            await bootstrap_mubit_agents(default_specs())
        except Exception as exc:
            logger.warning("MuBit agent bootstrap raised: %s", exc)

    return app


app = create_app()
