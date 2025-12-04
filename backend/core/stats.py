"""
Anonymous statistics counter.
Stores only aggregate counts - no personal data, IPs, or timestamps.
"""

import json
from pathlib import Path
from threading import Lock

STATS_FILE = Path(__file__).parent.parent.parent / "data" / "stats.json"

# Thread-safe lock for file operations
_lock = Lock()


def _ensure_stats_file():
    """Ensure stats file and directory exist."""
    STATS_FILE.parent.mkdir(parents=True, exist_ok=True)
    if not STATS_FILE.exists():
        STATS_FILE.write_text(json.dumps({
            "installs_started": 0,
            "installs_completed": 0,
            "script_downloads": 0,
        }))


def _read_stats() -> dict:
    """Read current stats."""
    _ensure_stats_file()
    try:
        return json.loads(STATS_FILE.read_text())
    except (json.JSONDecodeError, FileNotFoundError):
        return {
            "installs_started": 0,
            "installs_completed": 0,
            "script_downloads": 0,
        }


def _write_stats(stats: dict):
    """Write stats to file."""
    _ensure_stats_file()
    STATS_FILE.write_text(json.dumps(stats, indent=2))


def increment(counter: str) -> int:
    """
    Increment a counter and return the new value.

    Valid counters: installs_started, installs_completed, script_downloads
    """
    with _lock:
        stats = _read_stats()
        if counter in stats:
            stats[counter] += 1
            _write_stats(stats)
            return stats[counter]
        return 0


def get_stats() -> dict:
    """Get all stats (read-only, for display)."""
    with _lock:
        return _read_stats()


def get_count(counter: str) -> int:
    """Get a specific counter value."""
    with _lock:
        stats = _read_stats()
        return stats.get(counter, 0)
