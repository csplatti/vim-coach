"""Best-effort status file shared by the worker and local review app."""

from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
from typing import Any


def status_path() -> Path:
    configured = os.environ.get("VIM_COACH_STATUS_FILE")
    if configured:
        return Path(configured).expanduser()
    return Path.home() / ".local" / "state" / "vim-coach" / "status.json"


def write_status(state: str, batch_id: Any = None, **details: Any) -> None:
    path = status_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    value = {
        "state": state,
        "batchId": batch_id,
        "updatedAt": datetime.now(timezone.utc).isoformat(),
        **details,
    }
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(value, indent=2) + "\n")
    temporary.replace(path)
