"""Local orchestration from provider candidates to verified suggestions."""

from __future__ import annotations

from typing import Any

from replay.verify import verify


SEMANTIC_MOTIONS = ("w", "b", "e", "W", "B", "E", "ge", "gg", "G", "0", "^", "$", "%")
COUNTABLE_MOTIONS = {"h", "j", "k", "l", "w", "b", "e", "W", "B", "E"}
LOCAL_MOTION_PRIORITY = {
    "%": 90,
    "gg": 85,
    "G": 85,
    "$": 80,
    "^": 80,
    "0": 75,
    "W": 65,
    "B": 65,
    "E": 65,
    "ge": 65,
    "w": 50,
    "b": 50,
    "e": 50,
}


def _token_objects(compiled: list[str]) -> list[dict[str, Any]]:
    tokens: list[dict[str, Any]] = []
    index = 0
    while index < len(compiled):
        if compiled[index].isdigit() and compiled[index] != "0":
            digits = []
            while index < len(compiled) and compiled[index].isdigit():
                digits.append(compiled[index])
                index += 1
            tokens.append({"kind": "count", "value": int("".join(digits))})
            continue
        value = compiled[index]
        if value == "g" and index + 1 < len(compiled) and compiled[index + 1] in {"g", "e"}:
            tokens.append({"kind": "move", "key": value + compiled[index + 1]})
            index += 2
            continue
        if value in {"h", "j", "k", "l", "w", "b", "e", "W", "B", "E", "G", "0", "^", "$", "%"}:
            tokens.append({"kind": "move", "key": value})
            index += 1
            continue
        if value in {"x", "D"}:
            tokens.append({"kind": "delete", "command": value})
            index += 1
            continue
        command = "".join(compiled[index:index + 3])
        if command in {"diw", "daw"}:
            tokens.append({"kind": "delete", "command": command})
            index += 3
            continue
        command = "".join(compiled[index:index + 2])
        if command in {"dd", "dw"}:
            tokens.append({"kind": "delete", "command": command})
            index += 2
            continue
        return []
    return tokens


def _compressed_motion_candidate(original: list[str]) -> list[str] | None:
    compressed: list[str] = []
    changed = False
    index = 0
    while index < len(original):
        token = original[index]
        end = index + 1
        while end < len(original) and original[end] == token:
            end += 1
        count = end - index
        if token in COUNTABLE_MOTIONS and count >= 3:
            replacement = [*str(count), token]
            if len(replacement) < count:
                compressed.extend(replacement)
                changed = True
            else:
                compressed.extend(original[index:end])
        else:
            compressed.extend(original[index:end])
        index = end
    return compressed if changed and len(compressed) < len(original) else None


def augment_local_candidates(
    episodes: list[dict[str, Any]], suggestions: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Add bounded local possibilities; replay still decides equivalence."""
    by_id = {
        suggestion.get("episodeId"): {
            **suggestion,
            "candidates": list(suggestion.get("candidates", [])),
        }
        for suggestion in suggestions
    }
    for episode in episodes:
        suggestion = by_id.setdefault(episode.get("id"), {
            "episodeId": episode.get("id"),
            "candidates": [],
        })
        existing = {
            tuple(candidate.get("compiledTokens", []))
            for candidate in suggestion["candidates"]
        }
        if episode.get("kind") == "navigation":
            for key in SEMANTIC_MOTIONS:
                compiled_key = tuple(key)
                if compiled_key in existing:
                    continue
                suggestion["candidates"].append({
                    "tokens": [{"kind": "move", "key": key}],
                    "compiledTokens": list(key),
                    "concept": key,
                    "explanation": "",
                    "_rankingPriority": LOCAL_MOTION_PRIORITY[key],
                })
        compressed = _compressed_motion_candidate(episode.get("resolvedTokens", []))
        if compressed and tuple(compressed) not in existing:
            suggestion["candidates"].append({
                "tokens": _token_objects(compressed),
                "compiledTokens": compressed,
                "concept": "count",
                "explanation": "",
                "_rankingPriority": 10,
            })
    return list(by_id.values())


def verify_candidates(
    episode: dict[str, Any],
    candidates: list[dict[str, Any]],
    diagnostics: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    verified: list[dict[str, Any]] = []
    for candidate in candidates:
        candidate_to_verify = candidate
        try:
            result = verify({
                "schemaVersion": 1,
                "before": episode["before"],
                "after": episode["after"],
                "originalTokens": episode["resolvedTokens"],
                "candidateTokens": candidate_to_verify["compiledTokens"],
            })

            # Reasoning models sometimes describe counted motion from column 0
            # but omit the original leading positioning command. Try restoring
            # that one safe prefix; replay remains the authority on equivalence.
            original_tokens = episode["resolvedTokens"]
            candidate_tokens = candidate_to_verify["compiledTokens"]
            if (
                not result.get("accepted")
                and original_tokens
                and original_tokens[0] in {"0", "^", "$"}
                and (not candidate_tokens or candidate_tokens[0] != original_tokens[0])
            ):
                repaired_tokens = [original_tokens[0], *candidate_tokens]
                if len(repaired_tokens) < len(original_tokens):
                    repaired_result = verify({
                        "schemaVersion": 1,
                        "before": episode["before"],
                        "after": episode["after"],
                        "originalTokens": original_tokens,
                        "candidateTokens": repaired_tokens,
                    })
                    if repaired_result.get("accepted"):
                        candidate_to_verify = {
                            **candidate_to_verify,
                            "tokens": [
                                {"kind": "move", "key": original_tokens[0]},
                                *candidate_to_verify.get("tokens", []),
                            ],
                            "compiledTokens": repaired_tokens,
                        }
                        result = repaired_result
        except (KeyError, TypeError, ValueError, RuntimeError) as error:
            if diagnostics is not None:
                diagnostics.append({
                    "episodeId": episode.get("id"),
                    "candidateTokens": candidate.get("compiledTokens", []),
                    "reason": f"replay error: {error}",
                })
            continue
        if not result.get("accepted"):
            if diagnostics is not None:
                diagnostics.append({
                    "episodeId": episode.get("id"),
                    "candidateTokens": candidate.get("compiledTokens", []),
                    "reason": result.get("rejectionReason", "replay rejected candidate"),
                    "originalMismatchFields": result.get("originalMismatchFields", []),
                    "candidateMismatchFields": result.get("candidateMismatchFields", []),
                })
            continue
        verified.append({
            **candidate_to_verify,
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
    verified.sort(key=lambda item: (
        -item["savedLogicalKeys"],
        -item.get("_rankingPriority", 100),
        item["candidateLogicalKeys"],
    ))
    return verified[:3]


def verify_batch_candidates(
    episodes: list[dict[str, Any]],
    suggestions: list[dict[str, Any]],
    diagnostics: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    by_id = {episode.get("id"): episode for episode in episodes}
    verified: list[dict[str, Any]] = []
    for suggestion in suggestions:
        episode = by_id.get(suggestion.get("episodeId"))
        if episode is None:
            continue
        verified.append({
            "episodeId": episode["id"],
            "candidates": verify_candidates(
                episode,
                suggestion.get("candidates", []),
                diagnostics,
            ),
        })
    return verified
