"""
Pydantic models for the Pi-hole Wizard Web API.
"""

from pydantic import BaseModel, Field
from typing import Optional, List
from enum import Enum


class DeploymentType(str, Enum):
    DOCKER = "docker"
    BARE_METAL = "bare-metal"


class UpstreamDNS(str, Enum):
    UNBOUND = "unbound"
    CLOUDFLARE = "cloudflare"
    GOOGLE = "google"
    QUAD9 = "quad9"
    CUSTOM = "custom"


class CheckStatus(str, Enum):
    PASS = "pass"
    FAIL = "fail"
    WARNING = "warning"
    CHECKING = "checking"


class CustomBlocklist(BaseModel):
    """A custom user-created blocklist."""
    id: str
    name: str
    description: Optional[str] = None
    domains: List[str] = []


class WizardState(BaseModel):
    """Current state of the wizard configuration."""
    deployment: Optional[DeploymentType] = None
    os: Optional[str] = None
    pihole_ip: Optional[str] = None
    network_interface: Optional[str] = None
    upstream_dns: UpstreamDNS = UpstreamDNS.UNBOUND
    enable_unbound: bool = True
    web_password: Optional[str] = None
    ipv6: bool = False
    dhcp_enabled: bool = False
    dhcp_start: Optional[str] = None
    dhcp_end: Optional[str] = None
    dhcp_router: Optional[str] = None
    custom_dns: Optional[str] = None
    blocklists: List[str] = []  # Selected blocklist preset IDs
    blocklist_exclusions: Optional[dict] = None  # { listId: [excluded domains] }
    blocklist_additions: Optional[dict] = None  # { listId: [added domains] }
    custom_blocklists: Optional[List[CustomBlocklist]] = None  # User-created lists


class PrerequisiteCheck(BaseModel):
    """Result of a single prerequisite check."""
    name: str
    status: CheckStatus
    message: str
    details: Optional[str] = None
    fix_suggestion: Optional[str] = None


class PrerequisiteResponse(BaseModel):
    """Response from prerequisite checking endpoint."""
    checks: List[PrerequisiteCheck]
    can_proceed: bool
    detected_ip: Optional[str] = None
    detected_interface: Optional[str] = None
    detected_gateway: Optional[str] = None
    is_static_ip: bool = False
    static_ip_message: Optional[str] = None


class ConfigFile(BaseModel):
    """A single generated configuration file."""
    filename: str
    content: str
    description: str


class ConfigPreviewResponse(BaseModel):
    """Response containing all generated config files for preview."""
    files: List[ConfigFile]
    commands_to_run: List[str]


class InstallStatus(BaseModel):
    """Current status of the installation process."""
    status: str  # idle, running, success, failed
    progress: int = Field(ge=0, le=100)
    current_step: str = ""
    error: Optional[str] = None


class ChatMessage(BaseModel):
    """A single chat message."""
    role: str  # user or assistant
    content: str


class ChatRequest(BaseModel):
    """Request to send a chat message."""
    message: str
    api_key: Optional[str] = None


class ChatResponse(BaseModel):
    """Response from chat endpoint."""
    response: str
