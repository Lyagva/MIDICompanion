"""Thread-safe registry for MIDI connections.

Why this exists:
- Companion's websocket image callback runs in a background thread.
- MIDI connections may be created/modified from another thread.
- Reading/writing a global list without synchronization can look "randomly empty".

Use `add_connection()`/`remove_connection()` to mutate, and `snapshot_connections()`
when iterating.
"""

from __future__ import annotations

import threading
from typing import List, TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from midi import Connection


_lock = threading.RLock()
_connections: List["Connection"] = []


def add_connection(conn: "Connection") -> None:
    with _lock:
        _connections.append(conn)


def remove_connection(conn: "Connection") -> None:
    with _lock:
        try:
            _connections.remove(conn)
        except ValueError:
            # Already removed / never added
            pass


def clear_connections() -> None:
    with _lock:
        _connections.clear()


def snapshot_connections() -> List["Connection"]:
    """Return a stable copy safe to iterate without holding the lock."""
    with _lock:
        return list(_connections)


def debug_state() -> dict:
    """Small helper for logging."""
    with _lock:
        return {
            "count": len(_connections),
            "ids": [id(c) for c in _connections],
            "names": [getattr(c, "name", "?") for c in _connections],
        }

