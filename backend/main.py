"""FastAPI application for the 31stFile Tax Position Advisor."""

from fastapi import FastAPI

from backend.routers import admin, health, research

app = FastAPI(
    title="31stFile Tax Position Advisor API",
    description=(
        "Preliminary retrieval of Indian direct-tax authorities. "
        "This API does not generate a certified tax advisory."
    ),
    version="0.1.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

app.include_router(health.router)
app.include_router(research.router)
app.include_router(admin.router)