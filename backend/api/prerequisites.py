"""
API routes for prerequisite checking.
"""

from fastapi import APIRouter

from backend.core.prerequisites import PrerequisiteChecker
from backend.models import PrerequisiteResponse

router = APIRouter()
checker = PrerequisiteChecker()


@router.get("", response_model=PrerequisiteResponse)
async def check_prerequisites():
    """Run all system prerequisite checks."""
    return checker.check_all()


@router.get("/network")
async def detect_network():
    """Detect network configuration."""
    ip, interface = checker.detect_network()
    gateway = checker.detect_gateway()

    return {
        "ip": ip,
        "interface": interface,
        "gateway": gateway,
        "suggested_dhcp_start": f"{'.'.join(ip.split('.')[:3])}.100" if ip else None,
        "suggested_dhcp_end": f"{'.'.join(ip.split('.')[:3])}.200" if ip else None,
    }
