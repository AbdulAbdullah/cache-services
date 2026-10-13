"""FastAPI application factory and main entry point."""
from fastapi import FastAPI

from app.api.routes.payload import router as payload_router

app = FastAPI(
    title="Caching Service",
    description="FastAPI Microservice for string transformation payload caching",
    version="0.1.0",
)

app.include_router(payload_router)


@app.get("/health", tags=["Health"])
async def health_check() -> dict[str, str]:
    """Health check endpoint to verify service is running."""
    return {"status": "ok"}
