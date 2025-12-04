"""
Pi-hole Wizard Web - Main FastAPI Application
"""

import os
from pathlib import Path
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from contextlib import asynccontextmanager

from backend.api import wizard, prerequisites, config, install, chat, update


# Get the project root directory
PROJECT_ROOT = Path(__file__).parent.parent
FRONTEND_DIR = PROJECT_ROOT / "frontend"
OUTPUT_DIR = PROJECT_ROOT / "output"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    # Ensure output directory exists
    OUTPUT_DIR.mkdir(exist_ok=True)
    yield


app = FastAPI(
    title="Pi-hole Wizard",
    description="Web-based Pi-hole & Unbound setup wizard with AI troubleshooting",
    version="1.0.0",
    lifespan=lifespan,
)

# Include API routers
app.include_router(wizard.router, prefix="/api/wizard", tags=["wizard"])
app.include_router(prerequisites.router, prefix="/api/prerequisites", tags=["prerequisites"])
app.include_router(config.router, prefix="/api/config", tags=["config"])
app.include_router(install.router, prefix="/api/install", tags=["install"])
app.include_router(chat.router, prefix="/api/chat", tags=["chat"])
app.include_router(update.router, prefix="/api/update", tags=["update"])

# Mount static files
app.mount("/css", StaticFiles(directory=FRONTEND_DIR / "css"), name="css")
app.mount("/js", StaticFiles(directory=FRONTEND_DIR / "js"), name="js")


@app.get("/")
async def serve_index():
    """Serve the main wizard page."""
    return FileResponse(FRONTEND_DIR / "index.html")


@app.get("/favicon.svg")
async def serve_favicon():
    """Serve the favicon."""
    return FileResponse(FRONTEND_DIR / "favicon.svg", media_type="image/svg+xml")


@app.get("/health")
async def health_check():
    """Health check endpoint for Docker."""
    return {"status": "healthy"}


def run():
    """Run the application with uvicorn."""
    import uvicorn
    uvicorn.run(
        "backend.main:app",
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 8080)),
        reload=os.environ.get("DEV", "").lower() == "true",
    )


if __name__ == "__main__":
    run()
