"""FastAPI entrypoint for the CafeTwin MVP."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app import config as _config
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
    return app


app = create_app()
