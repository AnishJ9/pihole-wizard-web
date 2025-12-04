"""
API routes for anonymous statistics.
"""

from fastapi import APIRouter
from fastapi.responses import PlainTextResponse

from backend.core.stats import get_stats, increment

router = APIRouter()


@router.get("")
async def get_statistics():
    """
    Get anonymous usage statistics.

    Returns only aggregate counts - no personal data.
    """
    stats = get_stats()
    return {
        "installs_started": stats.get("installs_started", 0),
        "installs_completed": stats.get("installs_completed", 0),
        "script_downloads": stats.get("script_downloads", 0),
    }


@router.post("/increment/{counter}")
async def increment_counter(counter: str):
    """
    Increment a counter.

    Valid counters: installs_started, installs_completed, script_downloads
    """
    valid_counters = ["installs_started", "installs_completed", "script_downloads"]
    if counter not in valid_counters:
        return {"error": f"Invalid counter. Valid: {valid_counters}"}

    new_value = increment(counter)
    return {"counter": counter, "value": new_value}


@router.get("/badge")
async def get_badge():
    """
    Get a shields.io compatible badge for installs.
    Can be used in README: ![Installs](https://your-domain.com/api/stats/badge)
    """
    stats = get_stats()
    count = stats.get("installs_completed", 0)

    # Format number nicely (1000 -> 1k, 1000000 -> 1M)
    if count >= 1000000:
        label = f"{count / 1000000:.1f}M"
    elif count >= 1000:
        label = f"{count / 1000:.1f}k"
    else:
        label = str(count)

    # Return shields.io JSON endpoint format
    return {
        "schemaVersion": 1,
        "label": "installs",
        "message": label,
        "color": "brightgreen"
    }
