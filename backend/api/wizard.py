"""
API routes for wizard state management.
"""

from fastapi import APIRouter, HTTPException
from typing import Dict, Any

from backend.models import WizardState

router = APIRouter()

# In-memory session storage (for simplicity)
# In production, you might want Redis or a database
_sessions: Dict[str, WizardState] = {}
_default_session = "default"


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
