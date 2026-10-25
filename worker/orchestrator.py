"""Local orchestration from catalog/provider candidates to verified lessons."""

from __future__ import annotations

from typing import Any

from replay.verify import verify_many
from worker.candidates import FEATURE_PRIORITY, merge_candidates


def augment_local_candidates(
    episodes: list[dict[str, Any]], suggestions: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Compatibility wrapper for the catalog-driven candidate generator."""
    return merge_candidates(episodes, suggestions)


def _candidate_feature(candidate: dict[str, Any]) -> str:
    explicit = candidate.get("_featureKey")
    if isinstance(explicit, str) and explicit:
        return explicit
    tokens = candidate.get("tokens", [])
    if any(isinstance(token, dict) and token.get("kind") == "count" for token in tokens):
        return "count"
    for kind, field in (("move", "key"), ("delete", "command")):
        for token in tokens:
            if isinstance(token, dict) and token.get("kind") == kind:
                value = token.get(field)
                if isinstance(value, str):
                    return value
    return ""


def _verification_payload(episode: dict[str, Any], token_sets: list[list[str]]) -> dict[str, Any]:
    return {
        "schemaVersion": 1,
        "before": episode["before"],
        "after": episode["after"],
        "originalTokens": episode["resolvedTokens"],
        "candidateTokenSets": token_sets,
        # Coaching compares the visible editing outcome. Register differences
        # are still measured and disclosed, but do not hide idiomatic commands
        # such as D or diw when they replace repeated x presses.
        "requireRegisterEquality": False,
    }


def _repair_positioning_prefix(
    episode: dict[str, Any], candidate: dict[str, Any], result: dict[str, Any]
) -> dict[str, Any] | None:
    original = episode.get("resolvedTokens", [])
    compiled = candidate.get("compiledTokens", [])
    if result.get("accepted") or not original or original[0] not in {"0", "^", "$"}:
        return None
    if compiled and compiled[0] == original[0]:
        return None
    repaired = [original[0], *compiled]
    if len(repaired) >= len(original):
        return None
    return {
        **candidate,
        "tokens": [{"kind": "move", "key": original[0]}, *candidate.get("tokens", [])],
        "compiledTokens": repaired,
        "_origin": "position-prefix-repair",
    }


def _verified_candidate(
    episode: dict[str, Any], candidate: dict[str, Any], result: dict[str, Any]
) -> dict[str, Any]:
    feature = _candidate_feature(candidate)
    return {
        **candidate,
        "_featureKey": feature,
        "_rankingPriority": candidate.get("_rankingPriority", FEATURE_PRIORITY.get(feature, 0)),
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
            "registersEqual": result.get("registersEqual", False),
            "comparisonPolicy": result.get("comparisonPolicy", "editing-outcome"),
            "profileId": episode.get("before", {}).get("profileId"),
            "replayLatencyMs": result["originalReplayLatencyMs"] + result["candidateReplayLatencyMs"],
        },
    }


def _record_rejection(
    diagnostics: list[dict[str, Any]] | None,
    episode: dict[str, Any],
    candidate: dict[str, Any],
    result: dict[str, Any],
) -> None:
    if diagnostics is None:
        return
    diagnostics.append({
        "episodeId": episode.get("id"),
        "candidateTokens": candidate.get("compiledTokens", []),
        "origin": candidate.get("_origin", "provider"),
        "reason": result.get("rejectionReason", "replay rejected candidate"),
        "originalMismatchFields": result.get("originalMismatchFields", []),
        "candidateMismatchFields": result.get("candidateMismatchFields", []),
    })


def verify_candidates(
    episode: dict[str, Any],
    candidates: list[dict[str, Any]],
    diagnostics: list[dict[str, Any]] | None = None,
    lesson_profile: dict[str, dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Replay candidates, deduplicate them, and apply curriculum-aware ranking."""
    unique: list[dict[str, Any]] = []
    seen: set[tuple[str, ...]] = set()
    for candidate in candidates:
        identity = tuple(candidate.get("compiledTokens", []))
        if not identity or identity in seen:
            continue
        seen.add(identity)
        unique.append(candidate)
    if not unique:
        return []

    try:
        results = verify_many(_verification_payload(
            episode,
            [candidate["compiledTokens"] for candidate in unique],
        ))
    except (KeyError, TypeError, ValueError, RuntimeError) as error:
        if diagnostics is not None:
            diagnostics.append({
                "episodeId": episode.get("id"),
                "candidateTokens": [],
                "reason": f"replay error: {error}",
            })
        return []

    verified: list[dict[str, Any]] = []
    repairs: list[dict[str, Any]] = []
    rejected: list[tuple[dict[str, Any], dict[str, Any]]] = []
    for candidate, result in zip(unique, results):
        if result.get("accepted"):
            verified.append(_verified_candidate(episode, candidate, result))
            continue
        repair = _repair_positioning_prefix(episode, candidate, result)
        if repair is not None and tuple(repair["compiledTokens"]) not in seen:
            seen.add(tuple(repair["compiledTokens"]))
            repairs.append(repair)
        rejected.append((candidate, result))

    repaired_identities: set[tuple[str, ...]] = set()
    if repairs:
        try:
            repair_results = verify_many(_verification_payload(
                episode,
                [candidate["compiledTokens"] for candidate in repairs],
            ))
        except (KeyError, TypeError, ValueError, RuntimeError):
            repair_results = []
        for candidate, result in zip(repairs, repair_results):
            if result.get("accepted"):
                verified.append(_verified_candidate(episode, candidate, result))
                repaired_identities.add(tuple(candidate["compiledTokens"][1:]))
            else:
                _record_rejection(diagnostics, episode, candidate, result)

    for candidate, result in rejected:
        if tuple(candidate.get("compiledTokens", [])) not in repaired_identities:
            _record_rejection(diagnostics, episode, candidate, result)

    profile = lesson_profile or {}
    if lesson_profile is not None:
        # A review card introduces a feature once. "I know" and dismissal are
        # represented in the same exposure history, so neither can reappear as
        # another duplicate lesson.
        verified = [
            item for item in verified
            if int(profile.get(_candidate_feature(item), {}).get("exposures", 0)) == 0
        ]
    verified.sort(key=lambda item: (
        -item["savedLogicalKeys"],
        -item.get("_rankingPriority", 0),
        item["candidateLogicalKeys"],
    ))
    return verified[:3]


def verify_batch_candidates(
    episodes: list[dict[str, Any]],
    suggestions: list[dict[str, Any]],
    diagnostics: list[dict[str, Any]] | None = None,
    lesson_profile: dict[str, dict[str, Any]] | None = None,
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
                lesson_profile,
            ),
        })
    return verified
