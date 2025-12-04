"""
System prerequisite checker for Pi-hole installation.
Detects Docker, available ports, network configuration.
"""

import shutil
import socket
import subprocess
import platform
import re
from typing import Optional, Tuple, List, Dict, TYPE_CHECKING

from backend.models import PrerequisiteCheck, PrerequisiteResponse, CheckStatus

if TYPE_CHECKING:
    from backend.core.ssh_manager import SSHManager


class PrerequisiteChecker:
    """Check system prerequisites for Pi-hole installation."""

    async def check_all_async(self, ssh_manager: "SSHManager") -> PrerequisiteResponse:
        """Run all prerequisite checks, using SSH if connected."""
        # If SSH is connected or we're running locally on Pi, use the ssh_manager
        if ssh_manager.is_connected() or ssh_manager.is_running_on_pi():
            return await self._check_all_via_ssh(ssh_manager)
        else:
            # Local checks (no SSH)
            return self.check_all()

    async def _check_all_via_ssh(self, ssh_manager: "SSHManager") -> PrerequisiteResponse:
        """Run prerequisite checks via SSH on the remote Pi."""
        checks = []

        # Check Docker
        docker_check = await self._check_docker_ssh(ssh_manager)
        checks.append(docker_check)

        # Check Docker Compose
        compose_check = await self._check_docker_compose_ssh(ssh_manager)
        checks.append(compose_check)

        # Check ports (via SSH)
        port53_check = await self._check_port_ssh(ssh_manager, 53, "DNS")
        checks.append(port53_check)

        port80_check = await self._check_port_ssh(ssh_manager, 80, "Web Interface")
        checks.append(port80_check)

        # Detect network info via SSH
        detected_ip, detected_interface = await self._detect_network_ssh(ssh_manager)
        detected_gateway = await self._detect_gateway_ssh(ssh_manager)

        # For SSH connection, assume the connected IP is the Pi's IP
        if not detected_ip and ssh_manager.host:
            detected_ip = ssh_manager.host

        # Check static IP (simplified for remote)
        is_static, static_message = await self._check_static_ip_ssh(ssh_manager, detected_interface)

        can_proceed = all(c.status != CheckStatus.FAIL for c in checks)

        return PrerequisiteResponse(
            checks=checks,
            can_proceed=can_proceed,
            detected_ip=detected_ip,
            detected_interface=detected_interface,
            detected_gateway=detected_gateway,
            is_static_ip=is_static,
            static_ip_message=static_message,
        )

    async def _check_docker_ssh(self, ssh_manager: "SSHManager") -> PrerequisiteCheck:
        """Check Docker via SSH."""
        try:
            returncode, stdout, stderr = await ssh_manager.run_command("which docker")
            if returncode != 0:
                return PrerequisiteCheck(
                    name="Docker",
                    status=CheckStatus.FAIL,
                    message="Docker not installed",
                    details="Docker is required for the recommended installation method.",
                    fix_suggestion="Install Docker: curl -fsSL https://get.docker.com | sh",
                )

            # Check if daemon is running
            returncode, stdout, stderr = await ssh_manager.run_command("docker info 2>&1")
            if returncode != 0:
                if "permission denied" in (stdout + stderr).lower():
                    return PrerequisiteCheck(
                        name="Docker",
                        status=CheckStatus.FAIL,
                        message="Docker permission denied",
                        details="User needs to be added to the docker group.",
                        fix_suggestion="Run: sudo usermod -aG docker $USER && newgrp docker",
                    )
                return PrerequisiteCheck(
                    name="Docker",
                    status=CheckStatus.FAIL,
                    message="Docker not running",
                    details="Docker is installed but the daemon is not running.",
                    fix_suggestion="Run: sudo systemctl start docker",
                )

            # Get version
            returncode, stdout, stderr = await ssh_manager.run_command("docker --version")
            version = stdout.strip() if returncode == 0 else "version unknown"

            return PrerequisiteCheck(
                name="Docker",
                status=CheckStatus.PASS,
                message="Docker is ready",
                details=version,
            )
        except Exception as e:
            return PrerequisiteCheck(
                name="Docker",
                status=CheckStatus.WARNING,
                message="Could not check Docker",
                details=str(e),
            )

    async def _check_docker_compose_ssh(self, ssh_manager: "SSHManager") -> PrerequisiteCheck:
        """Check Docker Compose via SSH."""
        try:
            # Try docker compose (v2)
            returncode, stdout, stderr = await ssh_manager.run_command("docker compose version 2>&1")
            if returncode == 0:
                return PrerequisiteCheck(
                    name="Docker Compose",
                    status=CheckStatus.PASS,
                    message="Docker Compose is ready",
                    details=stdout.strip(),
                )

            # Try docker-compose (v1)
            returncode, stdout, stderr = await ssh_manager.run_command("docker-compose --version 2>&1")
            if returncode == 0:
                return PrerequisiteCheck(
                    name="Docker Compose",
                    status=CheckStatus.PASS,
                    message="Docker Compose is ready",
                    details=stdout.strip(),
                )

            return PrerequisiteCheck(
                name="Docker Compose",
                status=CheckStatus.FAIL,
                message="Docker Compose not found",
                details="Docker Compose is required to run the containers.",
                fix_suggestion="Install: sudo apt-get install docker-compose-plugin",
            )
        except Exception as e:
            return PrerequisiteCheck(
                name="Docker Compose",
                status=CheckStatus.WARNING,
                message="Could not check Docker Compose",
                details=str(e),
            )

    async def _check_port_ssh(self, ssh_manager: "SSHManager", port: int, service_name: str) -> PrerequisiteCheck:
        """Check if a port is available via SSH."""
        try:
            # Check if port is in use
            returncode, stdout, stderr = await ssh_manager.run_command(
                f"ss -tuln | grep ':{port} ' || echo 'AVAILABLE'"
            )

            if "AVAILABLE" in stdout:
                return PrerequisiteCheck(
                    name=f"Port {port} ({service_name})",
                    status=CheckStatus.PASS,
                    message=f"Port {port} is available",
                )
            else:
                # Try to identify what's using the port
                returncode2, stdout2, stderr2 = await ssh_manager.run_command(
                    f"sudo lsof -i :{port} 2>/dev/null | head -2 || echo 'unknown'"
                )
                process = "unknown service"
                if stdout2 and "unknown" not in stdout2:
                    lines = stdout2.strip().split("\n")
                    if len(lines) > 1:
                        process = lines[1].split()[0]

                return PrerequisiteCheck(
                    name=f"Port {port} ({service_name})",
                    status=CheckStatus.FAIL,
                    message=f"Port {port} is in use",
                    details=f"Another process is using this port: {process}",
                    fix_suggestion=f"Stop the service using port {port} before installing Pi-hole.",
                )
        except Exception as e:
            return PrerequisiteCheck(
                name=f"Port {port} ({service_name})",
                status=CheckStatus.WARNING,
                message=f"Could not check port {port}",
                details=str(e),
            )

    async def _detect_network_ssh(self, ssh_manager: "SSHManager") -> Tuple[Optional[str], Optional[str]]:
        """Detect network configuration via SSH."""
        try:
            # Get default route interface and IP
            returncode, stdout, stderr = await ssh_manager.run_command(
                "ip route show default | awk '/default/ {print $5}'"
            )
            interface = stdout.strip() if returncode == 0 and stdout.strip() else None

            if interface:
                returncode, stdout, stderr = await ssh_manager.run_command(
                    f"ip -4 addr show {interface} | grep -oP 'inet \\K[0-9.]+'"
                )
                ip = stdout.strip() if returncode == 0 and stdout.strip() else None
                return ip, interface

            # Fallback: get any non-loopback IP
            returncode, stdout, stderr = await ssh_manager.run_command(
                "hostname -I | awk '{print $1}'"
            )
            ip = stdout.strip() if returncode == 0 and stdout.strip() else None
            return ip, None
        except Exception:
            return None, None

    async def _detect_gateway_ssh(self, ssh_manager: "SSHManager") -> Optional[str]:
        """Detect default gateway via SSH."""
        try:
            returncode, stdout, stderr = await ssh_manager.run_command(
                "ip route show default | awk '/default/ {print $3}'"
            )
            return stdout.strip() if returncode == 0 and stdout.strip() else None
        except Exception:
            return None

    async def _check_static_ip_ssh(self, ssh_manager: "SSHManager", interface: Optional[str]) -> Tuple[bool, str]:
        """Check if IP is static via SSH."""
        try:
            # Check dhcpcd.conf
            returncode, stdout, stderr = await ssh_manager.run_command(
                "grep -q 'static ip_address' /etc/dhcpcd.conf 2>/dev/null && echo 'STATIC'"
            )
            if "STATIC" in stdout:
                return True, "Static IP configured in /etc/dhcpcd.conf"

            # Check for DHCP client running
            returncode, stdout, stderr = await ssh_manager.run_command(
                "pgrep -x 'dhclient|dhcpcd' >/dev/null && echo 'DHCP'"
            )
            if "DHCP" in stdout:
                return False, "DHCP client is running - IP may change"

            return False, "Could not confirm static IP configuration"
        except Exception:
            return False, "Could not check static IP configuration"

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

        # Check if IP is static
        is_static, static_message = self.check_static_ip(detected_interface)

        can_proceed = all(c.status != CheckStatus.FAIL for c in checks)

        return PrerequisiteResponse(
            checks=checks,
            can_proceed=can_proceed,
            detected_ip=detected_ip,
            detected_interface=detected_interface,
            detected_gateway=detected_gateway,
            is_static_ip=is_static,
            static_ip_message=static_message,
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

    def check_static_ip(self, interface: Optional[str] = None) -> Tuple[bool, str]:
        """
        Check if the current IP appears to be static or DHCP-assigned.
        Returns (is_static, message).
        """
        # Check dhcpcd.conf (Raspberry Pi OS / Debian)
        try:
            with open("/etc/dhcpcd.conf", "r") as f:
                content = f.read()
                if "static ip_address" in content:
                    return True, "Static IP configured in /etc/dhcpcd.conf"
        except FileNotFoundError:
            pass
        except Exception:
            pass

        # Check netplan (Ubuntu)
        try:
            import glob
            for netplan_file in glob.glob("/etc/netplan/*.yaml"):
                with open(netplan_file, "r") as f:
                    content = f.read()
                    if "addresses:" in content and "dhcp4: false" in content.lower():
                        return True, f"Static IP configured in {netplan_file}"
                    if "addresses:" in content and "dhcp4:" not in content.lower():
                        return True, f"Static IP configured in {netplan_file}"
        except Exception:
            pass

        # Check NetworkManager (various distros)
        if interface:
            try:
                result = subprocess.run(
                    ["nmcli", "-t", "-f", "ipv4.method", "connection", "show", interface],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                if result.returncode == 0 and "manual" in result.stdout.lower():
                    return True, "Static IP configured via NetworkManager"
            except Exception:
                pass

        # Check /etc/network/interfaces (older Debian)
        try:
            with open("/etc/network/interfaces", "r") as f:
                content = f.read()
                if "static" in content and interface and interface in content:
                    return True, "Static IP configured in /etc/network/interfaces"
        except FileNotFoundError:
            pass
        except Exception:
            pass

        # Check for active DHCP lease (indicates DHCP is being used)
        try:
            result = subprocess.run(
                ["ps", "aux"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if "dhclient" in result.stdout or "dhcpcd" in result.stdout:
                return False, "DHCP client is running - IP may change"
        except Exception:
            pass

        # Couldn't determine - assume DHCP for safety
        return False, "Could not confirm static IP configuration"

    def is_raspberry_pi(self) -> bool:
        """Check if the current machine is a Raspberry Pi."""
        # Check /proc/cpuinfo for Raspberry Pi
        try:
            with open("/proc/cpuinfo", "r") as f:
                cpuinfo = f.read().lower()
                if "raspberry" in cpuinfo or "bcm" in cpuinfo:
                    return True
        except Exception:
            pass

        # Check /proc/device-tree/model
        try:
            with open("/proc/device-tree/model", "r") as f:
                model = f.read().lower()
                if "raspberry" in model:
                    return True
        except Exception:
            pass

        # Check hostname
        try:
            hostname = socket.gethostname().lower()
            if "raspberry" in hostname or "pi" in hostname:
                return True
        except Exception:
            pass

        # Check architecture (ARM is a hint but not definitive)
        arch = platform.machine().lower()
        if arch in ("aarch64", "armv7l", "armv6l"):
            # ARM architecture, could be a Pi
            # Do additional check for Debian/Raspbian
            try:
                with open("/etc/os-release", "r") as f:
                    os_info = f.read().lower()
                    if "raspbian" in os_info or "raspberry" in os_info:
                        return True
            except Exception:
                pass

        return False

    def scan_for_raspberry_pis(self) -> List[Dict[str, str]]:
        """Scan the local network for Raspberry Pi devices."""
        found_pis = []

        # Get the local network subnet
        local_ip, _ = self.detect_network()
        if not local_ip:
            return found_pis

        # Try mDNS/Bonjour first (raspberrypi.local)
        mdns_hosts = ["raspberrypi.local", "raspberrypi4.local", "raspberrypi5.local", "pihole.local"]
        for hostname in mdns_hosts:
            try:
                ip = socket.gethostbyname(hostname)
                if ip and ip != local_ip:
                    found_pis.append({
                        "ip": ip,
                        "hostname": hostname,
                        "method": "mDNS"
                    })
            except socket.gaierror:
                pass

        # Try ARP scan if we have arp command
        try:
            result = subprocess.run(
                ["arp", "-a"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                # Parse ARP table looking for Raspberry Pi MAC prefixes
                # Raspberry Pi Foundation OUI prefixes
                pi_mac_prefixes = [
                    "b8:27:eb",  # RPi Foundation
                    "dc:a6:32",  # RPi Foundation
                    "e4:5f:01",  # RPi Foundation
                    "d8:3a:dd",  # RPi 4/5
                    "2c:cf:67",  # RPi 5
                ]
                for line in result.stdout.split("\n"):
                    line_lower = line.lower()
                    for prefix in pi_mac_prefixes:
                        if prefix in line_lower:
                            # Extract IP from ARP output
                            # Format varies: "hostname (192.168.1.x) at aa:bb:cc:dd:ee:ff"
                            ip_match = re.search(r'\((\d+\.\d+\.\d+\.\d+)\)', line)
                            if ip_match:
                                ip = ip_match.group(1)
                                if ip != local_ip and not any(p["ip"] == ip for p in found_pis):
                                    found_pis.append({
                                        "ip": ip,
                                        "hostname": None,
                                        "method": "ARP (MAC prefix)"
                                    })
                            break
        except Exception:
            pass

        # Try nmap ping scan if available (more thorough but slower)
        if not found_pis:
            try:
                subnet = ".".join(local_ip.split(".")[:3]) + ".0/24"
                result = subprocess.run(
                    ["nmap", "-sn", subnet, "--host-timeout", "1s"],
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                if result.returncode == 0:
                    # Look for Raspberry Pi in nmap output
                    current_ip = None
                    for line in result.stdout.split("\n"):
                        if "Nmap scan report for" in line:
                            ip_match = re.search(r'(\d+\.\d+\.\d+\.\d+)', line)
                            if ip_match:
                                current_ip = ip_match.group(1)
                        if current_ip and "raspberry" in line.lower():
                            if current_ip != local_ip and not any(p["ip"] == current_ip for p in found_pis):
                                found_pis.append({
                                    "ip": current_ip,
                                    "hostname": None,
                                    "method": "nmap"
                                })
            except Exception:
                pass

        return found_pis

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
