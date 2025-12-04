"""
API routes for wizard state management.
"""

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from typing import Dict, Any
from datetime import datetime

from backend.models import WizardState

router = APIRouter()

# In-memory session storage (for simplicity)
# In production, you might want Redis or a database
_sessions: Dict[str, WizardState] = {}
_default_session = "default"

# Export format version for future compatibility
EXPORT_VERSION = "1.0"


@router.get("/state", response_model=WizardState)
async def get_wizard_state():
    """Get the current wizard state."""
    if _default_session not in _sessions:
        _sessions[_default_session] = WizardState()
    return _sessions[_default_session]


@router.post("/state", response_model=WizardState)
async def update_wizard_state(state: WizardState):
    """Update the wizard state."""
    _sessions[_default_session] = state
    return state


@router.patch("/state", response_model=WizardState)
async def patch_wizard_state(updates: Dict[str, Any]):
    """Partially update the wizard state."""
    if _default_session not in _sessions:
        _sessions[_default_session] = WizardState()

    current = _sessions[_default_session]
    current_dict = current.model_dump()
    current_dict.update(updates)

    try:
        _sessions[_default_session] = WizardState(**current_dict)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    return _sessions[_default_session]


@router.delete("/state")
async def reset_wizard_state():
    """Reset the wizard state to defaults."""
    _sessions[_default_session] = WizardState()
    return {"message": "Wizard state reset"}


@router.get("/export")
async def export_wizard_state():
    """Export the wizard state as a downloadable JSON file."""
    if _default_session not in _sessions:
        _sessions[_default_session] = WizardState()

    state = _sessions[_default_session]

    # Create export object with metadata
    export_data = {
        "version": EXPORT_VERSION,
        "exported_at": datetime.utcnow().isoformat(),
        "settings": state.model_dump()
    }

    # Remove sensitive data from export
    if export_data["settings"].get("web_password"):
        export_data["settings"]["web_password"] = None
        export_data["_note"] = "Password was not exported for security. You'll need to set it again."

    return JSONResponse(
        content=export_data,
        headers={
            "Content-Disposition": "attachment; filename=pihole-wizard-config.json"
        }
    )


@router.post("/import")
async def import_wizard_state(import_data: Dict[str, Any]):
    """Import wizard state from a previously exported JSON file."""
    # Validate import format
    if "version" not in import_data or "settings" not in import_data:
        raise HTTPException(
            status_code=400,
            detail="Invalid import file format. Please use a file exported from Pi-hole Wizard."
        )

    # Check version compatibility
    version = import_data.get("version", "0")
    if not version.startswith("1."):
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported export version: {version}. This wizard supports version 1.x"
        )

    settings = import_data["settings"]

    try:
        # Validate and create state from imported settings
        _sessions[_default_session] = WizardState(**settings)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid settings: {str(e)}")

    return {
        "message": "Configuration imported successfully",
        "imported_at": import_data.get("exported_at", "Unknown"),
        "state": _sessions[_default_session]
    }
