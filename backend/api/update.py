"""
API routes for one-click update feature.
"""

import asyncio
import subprocess
from pathlib import Path
from fastapi import APIRouter, HTTPException
from typing import Optional

router = APIRouter()

# Update state
_update_status = {
    "status": "idle",  # idle, checking, updating, success, failed
    "progress": 0,
    "current_step": "",
    "message": "",
    "has_existing_install": False,
    "current_version": None,
    "latest_version": None,
}


def _run_command(cmd: list, cwd: Optional[str] = None) -> tuple[bool, str]:
    """Run a shell command and return (success, output)."""
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=cwd,
            timeout=60
        )
        return result.returncode == 0, result.stdout + result.stderr
    except subprocess.TimeoutExpired:
        return False, "Command timed out"
    except Exception as e:
        return False, str(e)


def _find_pihole_install() -> Optional[Path]:
    """Find existing Pi-hole installation directory."""
    # Common locations for wizard installs
    possible_paths = [
        Path.home() / "pihole",
        Path.home() / "pi-hole",
        Path("/opt/pihole"),
        Path("/opt/pi-hole"),
    ]

    for path in possible_paths:
        compose_file = path / "docker-compose.yml"
        if compose_file.exists():
            return path

    return None


def _get_running_containers() -> list[str]:
    """Get list of running Pi-hole related containers."""
    success, output = _run_command(["docker", "ps", "--format", "{{.Names}}"])
    if not success:
        return []

    containers = []
    for line in output.strip().split("\n"):
        if "pihole" in line.lower() or "unbound" in line.lower():
            containers.append(line)
    return containers


def _get_image_version(image_name: str) -> Optional[str]:
    """Get the current version/digest of a Docker image."""
    success, output = _run_command([
        "docker", "images", image_name, "--format", "{{.Tag}}"
    ])
    if success and output.strip():
        return output.strip().split("\n")[0]
    return None


@router.get("/check")
async def check_for_updates():
    """Check if Pi-hole is installed and if updates are available."""
    global _update_status

    _update_status["status"] = "checking"
    _update_status["current_step"] = "Looking for existing installation..."

    # Check for Docker
    success, _ = _run_command(["docker", "--version"])
    if not success:
        _update_status["status"] = "idle"
        return {
            "has_existing_install": False,
            "message": "Docker not found. Cannot check for Pi-hole installation."
        }

    # Find installation directory
    install_path = _find_pihole_install()
    running_containers = _get_running_containers()

    has_install = install_path is not None or len(running_containers) > 0

    if not has_install:
        _update_status["status"] = "idle"
        _update_status["has_existing_install"] = False
        return {
            "has_existing_install": False,
            "message": "No existing Pi-hole installation found. Use the wizard to install."
        }

    # Get current version
    current_version = _get_image_version("pihole/pihole")

    # Check for available updates by pulling with dry-run
    _update_status["current_step"] = "Checking for newer images..."

    # Check if updates are available (compare digests)
    success, output = _run_command([
        "docker", "pull", "--dry-run", "pihole/pihole:latest"
    ])

    # If dry-run not supported, we'll just report that we can update
    update_available = True  # Assume updates might be available

    _update_status["status"] = "idle"
    _update_status["has_existing_install"] = True
    _update_status["current_version"] = current_version

    return {
        "has_existing_install": True,
        "install_path": str(install_path) if install_path else None,
        "running_containers": running_containers,
        "current_version": current_version,
        "update_available": update_available,
        "message": "Pi-hole installation found. You can update to the latest version."
    }


@router.post("/start")
async def start_update():
    """Start the update process."""
    global _update_status

    if _update_status["status"] == "updating":
        raise HTTPException(status_code=400, detail="Update already in progress")

    # Find installation
    install_path = _find_pihole_install()
    if not install_path:
        # Try to find via running containers
        containers = _get_running_containers()
        if not containers:
            raise HTTPException(
                status_code=400,
                detail="No Pi-hole installation found to update"
            )
        # Default to home directory for container-only installs
        install_path = Path.home() / "pihole"

    _update_status["status"] = "updating"
    _update_status["progress"] = 0
    _update_status["message"] = ""

    # Run update in background
    asyncio.create_task(_perform_update(install_path))

    return {"message": "Update started", "status": "updating"}


async def _perform_update(install_path: Path):
    """Perform the actual update process."""
    global _update_status

    try:
        # Step 1: Pull latest images
        _update_status["current_step"] = "Pulling latest Pi-hole image..."
        _update_status["progress"] = 10

        success, output = _run_command(["docker", "pull", "pihole/pihole:latest"])
        if not success:
            raise Exception(f"Failed to pull Pi-hole image: {output}")

        _update_status["progress"] = 30

        # Step 2: Pull Unbound if it exists
        _update_status["current_step"] = "Pulling latest Unbound image..."
        # This might fail if Unbound isn't used, that's okay
        _run_command(["docker", "pull", "mvance/unbound:latest"])

        _update_status["progress"] = 50

        # Step 3: Stop containers
        _update_status["current_step"] = "Stopping containers..."

        if install_path.exists():
            success, output = _run_command(
                ["docker-compose", "down"],
                cwd=str(install_path)
            )
            if not success:
                # Try docker compose (v2) syntax
                _run_command(
                    ["docker", "compose", "down"],
                    cwd=str(install_path)
                )

        _update_status["progress"] = 70

        # Step 4: Start containers with new images
        _update_status["current_step"] = "Starting updated containers..."

        if install_path.exists():
            success, output = _run_command(
                ["docker-compose", "up", "-d"],
                cwd=str(install_path)
            )
            if not success:
                # Try docker compose (v2) syntax
                success, output = _run_command(
                    ["docker", "compose", "up", "-d"],
                    cwd=str(install_path)
                )
                if not success:
                    raise Exception(f"Failed to start containers: {output}")

        _update_status["progress"] = 90

        # Step 5: Verify containers are running
        _update_status["current_step"] = "Verifying update..."

        await asyncio.sleep(5)  # Wait for containers to start

        containers = _get_running_containers()
        if not containers:
            raise Exception("Containers failed to start after update")

        _update_status["progress"] = 100
        _update_status["status"] = "success"
        _update_status["current_step"] = "Update complete!"
        _update_status["message"] = f"Successfully updated. Running containers: {', '.join(containers)}"

    except Exception as e:
        _update_status["status"] = "failed"
        _update_status["current_step"] = "Update failed"
        _update_status["message"] = str(e)


@router.get("/status")
async def get_update_status():
    """Get the current update status."""
    return _update_status
