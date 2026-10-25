#!/usr/bin/env python3
"""JSON-line worker entry point for the local Vim Coach process."""

from __future__ import annotations

import json
import os
from pathlib import Path
import sys
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

if Path("/private/tmp").is_dir():
    os.environ["TMPDIR"] = "/private/tmp"

from worker.bitdeer import BitdeerClient, BitdeerError, BitdeerConfig
from worker.orchestrator import verify_candidates


def main() -> int:
    try:
        request: dict[str, Any] = json.load(sys.stdin)
        if request.get("schemaVersion") != 1:
            raise ValueError("unsupported worker schema version")
        if request.get("cloudEnabled") is not True:
            raise ValueError("cloud opt-in is required")
        episode = request.get("episode")
        if not isinstance(episode, dict):
            raise ValueError("episode must be an object")
        config = BitdeerConfig.from_env(cloud_enabled=True)
        result = BitdeerClient(config).propose(episode)
        result["candidates"] = verify_candidates(episode, result["candidates"])
        print(json.dumps({"ok": True, "episodeId": request.get("episodeId"), **result}, separators=(",", ":")))
        return 0
    except (OSError, json.JSONDecodeError, TypeError, ValueError, BitdeerError) as error:
        print(json.dumps({"ok": False, "error": str(error)}, separators=(",", ":")))
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
