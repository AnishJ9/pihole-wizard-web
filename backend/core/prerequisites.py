"""
System prerequisite checker for Pi-hole installation.
Detects Docker, available ports, network configuration.
"""

import shutil
import socket
import subprocess
from typing import Optional, Tuple

from backend.models import PrerequisiteCheck, PrerequisiteResponse, CheckStatus


class PrerequisiteChecker:
    """Check system prerequisites for Pi-hole installation."""

    def check_all(self) -> PrerequisiteResponse:
        """Run all prerequisite checks and return combined result."""
        checks = [
            self.check_docker(),
            self.check_docker_compose(),
            self.check_port_53(),
            self.check_port_80(),
        ]

        # Detect network info
        detected_ip, detected_interface = self.detect_network()
        detected_gateway = self.detect_gateway()

        can_proceed = all(c.status != CheckStatus.FAIL for c in checks)

        return PrerequisiteResponse(
            checks=checks,
            can_proceed=can_proceed,
            detected_ip=detected_ip,
            detected_interface=detected_interface,
            detected_gateway=detected_gateway,
        )

    def check_docker(self) -> PrerequisiteCheck:
        """Check if Docker is installed and running."""
        docker_path = shutil.which("docker")

        if not docker_path:
            return PrerequisiteCheck(
                name="Docker",
                status=CheckStatus.FAIL,
                message="Docker not installed",
                details="Docker is required for the recommended installation method.",
                fix_suggestion="Install Docker: https://docs.docker.com/get-docker/",
            )

        # Check if Docker daemon is running
        try:
            result = subprocess.run(
                ["docker", "info"],
                capture_output=True,
                timeout=10,
            )
            if result.returncode != 0:
                return PrerequisiteCheck(
                    name="Docker",
                    status=CheckStatus.FAIL,
                    message="Docker not running",
                    details="Docker is installed but the daemon is not running.",
                    fix_suggestion="Start Docker Desktop or run: sudo systemctl start docker",
                )
        except subprocess.TimeoutExpired:
            return PrerequisiteCheck(
                name="Docker",
                status=CheckStatus.WARNING,
                message="Docker check timed out",
                details="Could not verify Docker status.",
            )
        except Exception as e:
            return PrerequisiteCheck(
                name="Docker",
                status=CheckStatus.WARNING,
                message="Could not check Docker",
                details=str(e),
            )

        # Get Docker version
        try:
            result = subprocess.run(
                ["docker", "--version"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            version = result.stdout.strip()
        except Exception:
            version = "version unknown"

        return PrerequisiteCheck(
            name="Docker",
            status=CheckStatus.PASS,
            message="Docker is ready",
            details=version,
        )

    def check_docker_compose(self) -> PrerequisiteCheck:
        """Check if Docker Compose is available."""
        # Try docker compose (v2)
        try:
            result = subprocess.run(
                ["docker", "compose", "version"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                return PrerequisiteCheck(
                    name="Docker Compose",
                    status=CheckStatus.PASS,
                    message="Docker Compose is ready",
                    details=result.stdout.strip(),
                )
        except Exception:
            pass

        # Try docker-compose (v1)
        compose_path = shutil.which("docker-compose")
        if compose_path:
            try:
                result = subprocess.run(
                    ["docker-compose", "--version"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                return PrerequisiteCheck(
                    name="Docker Compose",
                    status=CheckStatus.PASS,
                    message="Docker Compose is ready",
                    details=result.stdout.strip(),
                )
            except Exception:
                pass

        return PrerequisiteCheck(
            name="Docker Compose",
            status=CheckStatus.FAIL,
            message="Docker Compose not found",
            details="Docker Compose is required to run the containers.",
            fix_suggestion="Docker Compose is included with Docker Desktop, or install separately.",
        )

    def check_port_53(self) -> PrerequisiteCheck:
        """Check if port 53 (DNS) is available."""
        return self._check_port(53, "DNS")

    def check_port_80(self) -> PrerequisiteCheck:
        """Check if port 80 (HTTP) is available."""
        return self._check_port(80, "Web Interface")

    def _check_port(self, port: int, service_name: str) -> PrerequisiteCheck:
        """Check if a specific port is available."""
        # Try to bind to the port
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1)
            result = sock.connect_ex(("127.0.0.1", port))
            sock.close()

            if result == 0:
                # Port is in use
                process = self._get_process_on_port(port)
                return PrerequisiteCheck(
                    name=f"Port {port} ({service_name})",
                    status=CheckStatus.FAIL,
                    message=f"Port {port} is in use",
                    details=f"Another process is using this port: {process}" if process else "Port is occupied by another service.",
                    fix_suggestion=f"Stop the service using port {port} or configure Pi-hole to use a different port.",
                )
            else:
                return PrerequisiteCheck(
                    name=f"Port {port} ({service_name})",
                    status=CheckStatus.PASS,
                    message=f"Port {port} is available",
                )
        except Exception as e:
            return PrerequisiteCheck(
                name=f"Port {port} ({service_name})",
                status=CheckStatus.WARNING,
                message=f"Could not check port {port}",
                details=str(e),
            )

    def _get_process_on_port(self, port: int) -> Optional[str]:
        """Try to identify what process is using a port."""
        try:
            # Try lsof on Unix-like systems
            result = subprocess.run(
                ["lsof", "-i", f":{port}"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0 and result.stdout:
                lines = result.stdout.strip().split("\n")
                if len(lines) > 1:
                    return lines[1].split()[0]  # Process name
        except Exception:
            pass
        return None

    def detect_network(self) -> Tuple[Optional[str], Optional[str]]:
        """Detect the primary network interface and IP address."""
        try:
            import netifaces
        except ImportError:
            # Fallback without netifaces
            return self._detect_network_fallback()

        try:
            # Get the default gateway interface
            gateways = netifaces.gateways()
            default_gateway = gateways.get("default", {}).get(netifaces.AF_INET)

            if default_gateway:
                interface = default_gateway[1]
                addrs = netifaces.ifaddresses(interface)

                if netifaces.AF_INET in addrs:
                    ip = addrs[netifaces.AF_INET][0].get("addr")
                    return ip, interface

            # Fallback: find any interface with an IP
            for iface in netifaces.interfaces():
                if iface == "lo":
                    continue
                addrs = netifaces.ifaddresses(iface)
                if netifaces.AF_INET in addrs:
                    ip = addrs[netifaces.AF_INET][0].get("addr")
                    if not ip.startswith("127."):
                        return ip, iface

        except Exception:
            pass

        return self._detect_network_fallback()

    def _detect_network_fallback(self) -> Tuple[Optional[str], Optional[str]]:
        """Fallback network detection without netifaces."""
        try:
            # Create a socket to detect default interface
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip, None
        except Exception:
            return None, None

    def detect_gateway(self) -> Optional[str]:
        """Detect the default gateway IP."""
        try:
            import netifaces
            gateways = netifaces.gateways()
            default_gateway = gateways.get("default", {}).get(netifaces.AF_INET)
            if default_gateway:
                return default_gateway[0]
        except Exception:
            pass

        # Fallback: try to parse route command
        try:
            result = subprocess.run(
                ["ip", "route", "show", "default"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                # Parse: "default via 192.168.1.1 dev eth0"
                parts = result.stdout.split()
                if "via" in parts:
                    idx = parts.index("via")
                    if idx + 1 < len(parts):
                        return parts[idx + 1]
        except Exception:
            pass

        # macOS fallback
        try:
            result = subprocess.run(
                ["netstat", "-rn"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                for line in result.stdout.split("\n"):
                    if line.startswith("default") or line.startswith("0.0.0.0"):
                        parts = line.split()
                        if len(parts) >= 2:
                            return parts[1]
        except Exception:
            pass

        return None
