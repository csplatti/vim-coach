"""Local orchestration from provider candidates to verified suggestions."""

from __future__ import annotations

from typing import Any

from replay.verify import verify


def verify_candidates(episode: dict[str, Any], candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    verified: list[dict[str, Any]] = []
    for candidate in candidates:
        try:
            result = verify({
                "schemaVersion": 1,
                "before": episode["before"],
                "after": episode["after"],
                "originalTokens": episode["resolvedTokens"],
                "candidateTokens": candidate["compiledTokens"],
            })
        except (KeyError, TypeError, ValueError, RuntimeError):
            continue
        if not result.get("accepted"):
            continue
        verified.append({
            **candidate,
            "verified": True,
            "originalTokens": episode["resolvedTokens"],
            "originalLogicalKeys": result["originalLogicalKeys"],
            "candidateLogicalKeys": result["candidateLogicalKeys"],
            "savedLogicalKeys": result["savedLogicalKeys"],
            "verification": {
                "accepted": True,
                "originalReplayMatches": result["originalReplayMatches"],
                "candidateReplayMatches": result["candidateReplayMatches"],
                "textEqual": True,
                "cursorEqual": True,
                "modeEqual": True,
                "registersEqual": True,
                "profileId": episode.get("before", {}).get("profileId"),
                "replayLatencyMs": result["originalReplayLatencyMs"] + result["candidateReplayLatencyMs"],
            },
        })
    verified.sort(key=lambda item: (-item["savedLogicalKeys"], item["candidateLogicalKeys"]))
    return verified[:3]
