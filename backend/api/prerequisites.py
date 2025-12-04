"""
API routes for prerequisite checking.
"""

from fastapi import APIRouter

from backend.core.prerequisites import PrerequisiteChecker
from backend.core.ssh_manager import ssh_manager
from backend.models import PrerequisiteResponse

router = APIRouter()
checker = PrerequisiteChecker()


@router.get("", response_model=PrerequisiteResponse)
async def check_prerequisites():
    """Run all system prerequisite checks.

    If SSH is connected, runs checks on the remote Pi.
    Otherwise, runs checks locally.
    """
    return await checker.check_all_async(ssh_manager)


@router.get("/network")
async def detect_network():
    """Detect network configuration.

    First checks if running on a Raspberry Pi. If not, scans network for Pis.
    """
    local_ip, interface = checker.detect_network()
    gateway = checker.detect_gateway()
    is_pi = checker.is_raspberry_pi()

    # If we're on a Pi, use local IP
    # Otherwise, try to find Pis on the network
    target_ip = local_ip
    target_hostname = None
    detected_pis = []
    detection_method = "local"

    if not is_pi:
        # Not running on a Pi, scan for Pis on network
        detected_pis = checker.scan_for_raspberry_pis()
        if detected_pis:
            # Use the first found Pi as default
            target_ip = detected_pis[0]["ip"]
            target_hostname = detected_pis[0].get("hostname")
            detection_method = detected_pis[0].get("method", "network_scan")

    return {
        "ip": target_ip,
        "interface": interface,
        "gateway": gateway,
        "suggested_dhcp_start": f"{'.'.join(target_ip.split('.')[:3])}.100" if target_ip else None,
        "suggested_dhcp_end": f"{'.'.join(target_ip.split('.')[:3])}.200" if target_ip else None,
        "is_raspberry_pi": is_pi,
        "local_ip": local_ip,
        "detected_pis": detected_pis,
        "target_hostname": target_hostname,
        "detection_method": detection_method,
    }
