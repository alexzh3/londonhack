"""FastAPI entrypoint for the CafeTwin MVP."""

from fastapi import FastAPI

from app.api.routes import router


app = FastAPI(title="CafeTwin MVP API")
app.include_router(router)
