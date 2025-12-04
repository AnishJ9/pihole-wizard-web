"""
API routes for one-click installation.
"""

import asyncio
import subprocess
from pathlib import Path
from typing import AsyncGenerator
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from backend.models import WizardState, InstallStatus
from backend.core.config_generator import ConfigGenerator

router = APIRouter()
generator = ConfigGenerator()

OUTPUT_DIR = Path(__file__).parent.parent.parent / "output"

# Global installation state
_install_status = InstallStatus(
    status="idle",
    progress=0,
    current_step="",
)


@router.get("/status", response_model=InstallStatus)
async def get_install_status():
    """Get current installation status."""
    return _install_status


@router.post("/start")
async def start_installation(state: WizardState):
    """Start the installation process."""
    global _install_status

    if _install_status.status == "running":
        return {"error": "Installation already in progress"}

    _install_status = InstallStatus(
        status="running",
        progress=0,
        current_step="Preparing...",
    )

    # Generate configs first
    config = state.model_dump()
    try:
        generator.save_all(config, OUTPUT_DIR)
    except Exception as e:
        _install_status = InstallStatus(
            status="failed",
            progress=0,
            current_step="Failed to generate configs",
            error=str(e),
        )
        return {"error": str(e)}

    return {"message": "Installation started", "status": "running"}


@router.websocket("/ws")
async def install_websocket(websocket: WebSocket):
    """WebSocket endpoint for live installation logs."""
    await websocket.accept()
    global _install_status

    try:
        # Wait for installation to start
        while _install_status.status == "idle":
            await asyncio.sleep(0.5)

        if _install_status.status != "running":
            await websocket.send_json({"type": "error", "message": "Installation not started"})
            return

        # Run installation steps
        async for log_line in run_installation():
            await websocket.send_json({"type": "log", "message": log_line})
            await asyncio.sleep(0.01)  # Small delay for UI

        # Send completion status
        await websocket.send_json({
            "type": "complete",
            "status": _install_status.status,
            "message": "Installation complete!" if _install_status.status == "success" else _install_status.error,
        })

    except WebSocketDisconnect:
        pass
    except Exception as e:
        await websocket.send_json({"type": "error", "message": str(e)})


async def run_installation() -> AsyncGenerator[str, None]:
    """Execute installation steps and yield log lines."""
    global _install_status

    steps = [
        ("Checking Docker...", 10, check_docker),
        ("Pulling Docker images...", 40, pull_images),
        ("Starting containers...", 70, start_containers),
        ("Verifying installation...", 90, verify_installation),
    ]

    try:
        for step_name, progress, step_func in steps:
            _install_status.current_step = step_name
            _install_status.progress = progress
            yield f"\n=== {step_name} ===\n"

            async for line in step_func():
                yield line

        _install_status = InstallStatus(
            status="success",
            progress=100,
            current_step="Complete!",
        )
        yield "\n=== Installation Complete! ===\n"

    except Exception as e:
        _install_status = InstallStatus(
            status="failed",
            progress=_install_status.progress,
            current_step="Failed",
            error=str(e),
        )
        yield f"\nERROR: {str(e)}\n"


async def check_docker() -> AsyncGenerator[str, None]:
    """Verify Docker is running."""
    result = subprocess.run(
        ["docker", "info"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise Exception("Docker is not running. Please start Docker and try again.")
    yield "Docker is running.\n"


async def pull_images() -> AsyncGenerator[str, None]:
    """Pull required Docker images."""
    images = ["pihole/pihole:latest", "mvance/unbound:latest"]

    for image in images:
        yield f"Pulling {image}...\n"

        process = await asyncio.create_subprocess_exec(
            "docker", "pull", image,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            cwd=OUTPUT_DIR,
        )

        async for line in process.stdout:
            yield line.decode()

        await process.wait()
        if process.returncode != 0:
            raise Exception(f"Failed to pull {image}")

        yield f"Pulled {image}\n"


async def start_containers() -> AsyncGenerator[str, None]:
    """Start containers with docker-compose."""
    yield "Running docker-compose up -d...\n"

    # Try docker compose (v2) first, fallback to docker-compose (v1)
    compose_cmd = ["docker", "compose"]
    result = subprocess.run(compose_cmd + ["version"], capture_output=True)
    if result.returncode != 0:
        compose_cmd = ["docker-compose"]

    process = await asyncio.create_subprocess_exec(
        *compose_cmd, "up", "-d",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
        cwd=OUTPUT_DIR,
    )

    async for line in process.stdout:
        yield line.decode()

    await process.wait()
    if process.returncode != 0:
        raise Exception("Failed to start containers")

    yield "Containers started.\n"


async def verify_installation() -> AsyncGenerator[str, None]:
    """Verify containers are running."""
    yield "Checking container status...\n"

    # Wait a moment for containers to initialize
    await asyncio.sleep(3)

    process = await asyncio.create_subprocess_exec(
        "docker", "ps", "--filter", "name=pihole", "--filter", "name=unbound",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )

    async for line in process.stdout:
        yield line.decode()

    await process.wait()

    # Check if pihole container is running
    result = subprocess.run(
        ["docker", "inspect", "-f", "{{.State.Running}}", "pihole"],
        capture_output=True,
        text=True,
    )

    if result.stdout.strip() != "true":
        raise Exception("Pi-hole container is not running")

    yield "\nPi-hole is running!\n"
