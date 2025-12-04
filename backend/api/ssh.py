"""
API routes for SSH connection management.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

from backend.core.ssh_manager import ssh_manager


router = APIRouter()


class SSHConnectRequest(BaseModel):
    """Request to connect via SSH."""
    host: str
    username: str
    password: str
    port: int = 22


class SSHStatusResponse(BaseModel):
    """SSH connection status."""
    is_local: bool
    is_connected: bool
    host: Optional[str] = None
    username: Optional[str] = None
    needs_ssh: bool  # True if running remotely and not connected


class SSHConnectResponse(BaseModel):
    """Response from SSH connect attempt."""
    success: bool
    message: str


@router.get("/status", response_model=SSHStatusResponse)
async def get_ssh_status():
    """
    Get current SSH connection status.
    Also indicates if we're running locally on a Pi (no SSH needed).
    """
    is_local = ssh_manager.is_running_on_pi()
    is_connected = ssh_manager.is_connected()

    return SSHStatusResponse(
        is_local=is_local,
        is_connected=is_connected,
        host=ssh_manager.host,
        username=ssh_manager.username,
        needs_ssh=not is_local and not is_connected,
    )


@router.post("/connect", response_model=SSHConnectResponse)
async def connect_ssh(request: SSHConnectRequest):
    """
    Establish SSH connection to remote Pi.
    """
    if ssh_manager.is_running_on_pi():
        return SSHConnectResponse(
            success=True,
            message="Running locally on Pi - no SSH needed",
        )

    success, message = await ssh_manager.connect(
        host=request.host,
        username=request.username,
        password=request.password,
        port=request.port,
    )

    return SSHConnectResponse(success=success, message=message)


@router.post("/disconnect")
async def disconnect_ssh():
    """Disconnect SSH session."""
    await ssh_manager.disconnect()
    return {"message": "Disconnected"}


@router.get("/test")
async def test_connection():
    """
    Test the SSH connection by running a simple command.
    """
    if ssh_manager.is_running_on_pi():
        return {"success": True, "message": "Running locally on Pi"}

    if not ssh_manager.is_connected():
        raise HTTPException(status_code=400, detail="Not connected to remote Pi")

    try:
        returncode, stdout, stderr = await ssh_manager.run_command("hostname")
        return {
            "success": returncode == 0,
            "hostname": stdout.strip(),
            "message": f"Connected to {stdout.strip()}",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/check-docker")
async def check_docker():
    """
    Check if Docker is installed and running on the target Pi.
    """
    if not ssh_manager.is_running_on_pi() and not ssh_manager.is_connected():
        raise HTTPException(status_code=400, detail="Not connected to remote Pi")

    docker_ok, docker_msg = await ssh_manager.check_docker()
    compose_ok, compose_msg = await ssh_manager.check_docker_compose()

    return {
        "docker": {"ok": docker_ok, "message": docker_msg},
        "compose": {"ok": compose_ok, "message": compose_msg},
    }
