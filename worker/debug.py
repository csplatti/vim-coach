"""Local JSONL debug stream for provider diagnostics."""

from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
from typing import Any


def debug_log_path() -> Path:
    configured = os.environ.get("VIM_COACH_DEBUG_LOG_FILE")
    if configured:
        return Path(configured).expanduser()
    return Path.home() / ".local" / "state" / "vim-coach" / "debug.jsonl"


def append_debug_event(kind: str, payload: dict[str, Any]) -> None:
    try:
        path = debug_log_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        event = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "kind": kind,
            "payload": payload,
        }
        with path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(event, separators=(",", ":")) + "\n")
    except (OSError, TypeError, ValueError):
        # Diagnostics must never break coaching.
        pass
