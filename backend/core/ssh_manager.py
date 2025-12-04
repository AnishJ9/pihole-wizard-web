"""
SSH connection manager for remote Pi-hole installation.
"""

import asyncio
import platform
import socket
from typing import Optional, AsyncGenerator, Tuple
import asyncssh


class SSHManager:
    """Manages SSH connections to remote Raspberry Pi."""

    def __init__(self):
        self.connection: Optional[asyncssh.SSHClientConnection] = None
        self.host: Optional[str] = None
        self.username: Optional[str] = None
        self._is_local: Optional[bool] = None

    def is_running_on_pi(self) -> bool:
        """Detect if we're running locally on a Raspberry Pi."""
        if self._is_local is not None:
            return self._is_local

        # Check architecture
        arch = platform.machine().lower()
        is_arm = arch in ('aarch64', 'armv7l', 'armv6l', 'arm64')

        if not is_arm:
            self._is_local = False
            return False

        # Check for Raspberry Pi specific files
        try:
            with open('/proc/cpuinfo', 'r') as f:
                cpuinfo = f.read().lower()
                if 'raspberry' in cpuinfo or 'bcm' in cpuinfo:
                    self._is_local = True
                    return True
        except:
            pass

        try:
            with open('/proc/device-tree/model', 'r') as f:
                model = f.read().lower()
                if 'raspberry' in model:
                    self._is_local = True
                    return True
        except:
            pass

        # Check for Raspbian/Raspberry Pi OS
        try:
            with open('/etc/os-release', 'r') as f:
                os_info = f.read().lower()
                if 'raspbian' in os_info or 'raspberry' in os_info:
                    self._is_local = True
                    return True
        except:
            pass

        self._is_local = False
        return False

    def is_connected(self) -> bool:
        """Check if SSH connection is active."""
        return self.connection is not None and not self.connection.is_closed()

    async def connect(self, host: str, username: str, password: str, port: int = 22) -> Tuple[bool, str]:
        """
        Establish SSH connection to remote Pi.
        Returns (success, message).
        """
        try:
            # Close existing connection if any
            if self.connection:
                self.connection.close()
                await self.connection.wait_closed()

            self.connection = await asyncssh.connect(
                host,
                port=port,
                username=username,
                password=password,
                known_hosts=None,  # Accept any host key (for home network use)
                connect_timeout=10,
            )

            self.host = host
            self.username = username

            # Test connection with a simple command
            result = await self.connection.run('echo "connected"', check=True)

            return True, f"Connected to {username}@{host}"

        except asyncssh.PermissionDenied:
            return False, "Authentication failed. Check username and password."
        except asyncssh.HostKeyNotVerifiable:
            return False, "Host key verification failed."
        except (OSError, asyncio.TimeoutError) as e:
            return False, f"Could not connect to {host}: Connection timed out or refused"
        except Exception as e:
            return False, f"Connection failed: {str(e)}"

    async def disconnect(self):
        """Close SSH connection."""
        if self.connection:
            self.connection.close()
            await self.connection.wait_closed()
            self.connection = None
            self.host = None
            self.username = None

    async def run_command(self, command: str, check: bool = False) -> Tuple[int, str, str]:
        """
        Run a command on the remote Pi.
        Returns (return_code, stdout, stderr).
        """
        if self.is_running_on_pi():
            # Run locally
            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate()
            return proc.returncode, stdout.decode(), stderr.decode()

        if not self.is_connected():
            raise Exception("Not connected to remote Pi")

        result = await self.connection.run(command, check=check)
        return result.returncode, result.stdout, result.stderr

    async def run_command_stream(self, command: str) -> AsyncGenerator[str, None]:
        """
        Run a command and stream output line by line.
        """
        if self.is_running_on_pi():
            # Run locally
            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
            )

            async for line in proc.stdout:
                yield line.decode()

            await proc.wait()
            return

        if not self.is_connected():
            raise Exception("Not connected to remote Pi")

        async with self.connection.create_process(command) as proc:
            async for line in proc.stdout:
                yield line
            async for line in proc.stderr:
                yield f"[stderr] {line}"

    async def upload_file(self, local_content: str, remote_path: str) -> Tuple[bool, str]:
        """
        Upload content to a file on the remote Pi.
        """
        if self.is_running_on_pi():
            # Write locally
            try:
                with open(remote_path, 'w') as f:
                    f.write(local_content)
                return True, f"Wrote {remote_path}"
            except Exception as e:
                return False, f"Failed to write {remote_path}: {e}"

        if not self.is_connected():
            return False, "Not connected to remote Pi"

        try:
            async with self.connection.start_sftp_client() as sftp:
                async with sftp.open(remote_path, 'w') as f:
                    await f.write(local_content)
            return True, f"Uploaded {remote_path}"
        except Exception as e:
            return False, f"Failed to upload {remote_path}: {e}"

    async def check_docker(self) -> Tuple[bool, str]:
        """Check if Docker is installed and running on the Pi."""
        returncode, stdout, stderr = await self.run_command("docker info 2>&1")

        if returncode != 0:
            if "command not found" in stdout + stderr:
                return False, "Docker is not installed"
            elif "permission denied" in (stdout + stderr).lower():
                return False, "Docker permission denied. User may need to be added to docker group."
            elif "Cannot connect" in stdout + stderr:
                return False, "Docker daemon is not running"
            else:
                return False, f"Docker check failed: {stdout or stderr}"

        return True, "Docker is running"

    async def check_docker_compose(self) -> Tuple[bool, str]:
        """Check if Docker Compose is available."""
        # Try docker compose (v2) first
        returncode, stdout, stderr = await self.run_command("docker compose version 2>&1")
        if returncode == 0:
            return True, stdout.strip()

        # Try docker-compose (v1)
        returncode, stdout, stderr = await self.run_command("docker-compose --version 2>&1")
        if returncode == 0:
            return True, stdout.strip()

        return False, "Docker Compose is not installed"


# Global SSH manager instance
ssh_manager = SSHManager()
