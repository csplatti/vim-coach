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

from worker.provider import LLMClient, LLMError, LLMConfig
from worker.debug import append_debug_event
from worker.history import append_verified_lessons, history_path, lesson_profile, related_lessons
from worker.orchestrator import augment_local_candidates, verify_batch_candidates, verify_candidates
from worker.status import write_status
from worker.vim_help import add_help_lessons


def main() -> int:
    request: dict[str, Any] = {}
    try:
        request: dict[str, Any] = json.load(sys.stdin)
        if request.get("schemaVersion") not in {1, 2}:
            raise ValueError("unsupported worker schema version")
        if request.get("cloudEnabled") is not True:
            raise ValueError("cloud opt-in is required")
        batch_id = request.get("batchId", request.get("episodeId"))
        _safe_status("running", batch_id, episodeCount=len(request.get("episodes", [])))
        if request.get("schemaVersion") == 1:
            config = LLMConfig.from_env(cloud_enabled=True)
            client = LLMClient(config)
            episode = request.get("episode")
            if not isinstance(episode, dict):
                raise ValueError("episode must be an object")
            result = client.propose(episode)
            result["candidates"] = verify_candidates(episode, result["candidates"])
            output = {"ok": True, "episodeId": request.get("episodeId"), **result}
            _safe_status("completed", batch_id, lessonCount=len(result["candidates"]))
        else:
            episodes = request.get("episodes")
            if not isinstance(episodes, list) or not episodes:
                raise ValueError("episodes must be a non-empty array")
            path = history_path()
            provider_warning = None
            try:
                config = LLMConfig.from_env(cloud_enabled=True)
                client = LLMClient(config)
                result = client.propose_batch(episodes, related_lessons(path, episodes))
            except LLMError as error:
                # Catalog generation and replay are useful even if a provider is
                # unavailable. Keep the batch moving and report the degradation.
                provider_warning = str(error)
                result = {
                    "model": "local-catalog",
                    "suggestions": [],
                    "providerReturnedContent": False,
                }
            provider_candidates = sum(
                len(suggestion.get("candidates", []))
                for suggestion in result["suggestions"]
            )
            candidates_to_verify = augment_local_candidates(episodes, result["suggestions"])
            local_candidates = sum(
                len(suggestion.get("candidates", []))
                for suggestion in candidates_to_verify
            ) - provider_candidates
            replay_rejections: list[dict[str, Any]] = []
            verified_suggestions = verify_batch_candidates(
                episodes,
                candidates_to_verify,
                replay_rejections,
                lesson_profile(path),
            )
            verified_suggestions = add_help_lessons(verified_suggestions)
            verified_candidates = sum(
                len(suggestion.get("candidates", []))
                for suggestion in verified_suggestions
            )
            history_warning = None
            try:
                persisted = append_verified_lessons(path, verified_suggestions, result["model"])
            except OSError as error:
                persisted = 0
                history_warning = f"could not persist lesson history: {error}"
            output = {
                "ok": True,
                "batchId": request.get("batchId"),
                "suggestions": verified_suggestions,
                "model": result["model"],
                "persistedLessons": persisted,
                "providerReturnedContent": result["providerReturnedContent"],
                "providerCandidateCount": provider_candidates,
                "localCandidateCount": local_candidates,
                "verifiedCandidateCount": verified_candidates,
                "replayRejections": replay_rejections,
            }
            if history_warning:
                output["historyWarning"] = history_warning
            if provider_warning:
                output["providerWarning"] = provider_warning
            _safe_status(
                "completed",
                batch_id,
                lessonCount=persisted,
                providerReturnedContent=result["providerReturnedContent"],
                providerCandidateCount=provider_candidates,
                localCandidateCount=local_candidates,
                verifiedCandidateCount=verified_candidates,
                replayRejections=replay_rejections,
                providerWarning=provider_warning,
            )
            if os.environ.get("VIM_COACH_DEBUG_PROMPT") == "1":
                append_debug_event(
                    "replay_result",
                    {
                        "providerCandidateCount": provider_candidates,
                        "localCandidateCount": local_candidates,
                        "verifiedCandidateCount": verified_candidates,
                        "rejections": replay_rejections,
                    },
                )
        print(json.dumps(output, separators=(",", ":")))
        return 0
    except (OSError, json.JSONDecodeError, TypeError, ValueError, LLMError) as error:
        _safe_status("error", request.get("batchId", request.get("episodeId")), message=str(error))
        print(json.dumps({"ok": False, "error": str(error)}, separators=(",", ":")))
        return 0


def _safe_status(state: str, batch_id: Any = None, **details: Any) -> None:
    try:
        write_status(state, batch_id, **details)
    except OSError:
        pass


if __name__ == "__main__":
    raise SystemExit(main())
