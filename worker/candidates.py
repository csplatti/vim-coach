"""Generate bounded, replay-safe candidates from the supported Vim catalog.

These are possibilities, not recommendations. The replay verifier remains the
authority on whether a candidate reaches the captured target.
"""

from __future__ import annotations

from typing import Any, Iterable


SEMANTIC_MOTIONS = ("w", "b", "e", "W", "B", "E", "ge", "gg", "G", "0", "^", "$", "%")
COUNTABLE_MOTIONS = {"h", "j", "k", "l", "w", "b", "e", "W", "B", "E"}
DELETE_COMMANDS = ("x", "D", "dd", "dw", "diw", "daw")
FEATURE_PRIORITY = {
    "%": 100,
    "diw": 95,
    "daw": 94,
    "D": 92,
    "dd": 90,
    "dw": 88,
    "gg": 86,
    "G": 86,
    "$": 84,
    "^": 82,
    "0": 80,
    "W": 72,
    "B": 72,
    "E": 72,
    "ge": 72,
    "w": 78,
    "b": 78,
    "e": 78,
    "count": 55,
    "x": 40,
}
MAX_LOCAL_CANDIDATES = 48


def token_objects(compiled: list[str]) -> list[dict[str, Any]]:
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
            if count <= 20 and len(replacement) < count:
                compressed.extend(replacement)
                changed = True
            else:
                compressed.extend(original[index:end])
        else:
            compressed.extend(original[index:end])
        index = end
    return compressed if changed and len(compressed) < len(original) else None


def _delete_suffix(original: list[str]) -> list[str] | None:
    for width in (3, 2, 1):
        suffix = original[-width:]
        if "".join(suffix) in DELETE_COMMANDS:
            return suffix
    return None


def _cursor(snapshot: dict[str, Any]) -> tuple[int, int]:
    cursor = snapshot.get("cursor", {})
    return int(cursor.get("row1Based", 1)), int(cursor.get("byteColumn0Based", 0))


def _targeted_motion(episode: dict[str, Any]) -> list[str] | None:
    before_row, before_col = _cursor(episode.get("before", {}))
    after_row, after_col = _cursor(episode.get("after", {}))
    if before_row == after_row:
        distance = after_col - before_col
        key = "l" if distance > 0 else "h"
    elif before_col == after_col:
        distance = after_row - before_row
        key = "j" if distance > 0 else "k"
    else:
        return None
    distance = abs(distance)
    if 2 <= distance <= 20:
        return [*str(distance), key]
    return None


def _feature_for(compiled: list[str]) -> str:
    objects = token_objects(compiled)
    if any(token.get("kind") == "count" for token in objects):
        return "count"
    for token in objects:
        if token.get("kind") == "move":
            return str(token.get("key"))
    for token in objects:
        if token.get("kind") == "delete":
            return str(token.get("command"))
    return ""


def _candidate(compiled: list[str], *, origin: str) -> dict[str, Any]:
    feature = _feature_for(compiled)
    return {
        "tokens": token_objects(compiled),
        "compiledTokens": compiled,
        "concept": feature,
        "explanation": "",
        "_featureKey": feature,
        "_origin": origin,
        "_rankingPriority": FEATURE_PRIORITY.get(feature, 0),
    }


def _programs(episode: dict[str, Any]) -> Iterable[tuple[list[str], str]]:
    original = episode.get("resolvedTokens", [])
    original_length = len(original)
    compressed = _compressed_motion_candidate(original)
    if compressed:
        yield compressed, "count-compression"

    if episode.get("kind") == "navigation":
        targeted = _targeted_motion(episode)
        if targeted:
            yield targeted, "cursor-delta"
        for motion in SEMANTIC_MOTIONS:
            yield list(motion), "feature-catalog"
        return

    suffix = _delete_suffix(original)
    for command in DELETE_COMMANDS:
        yield list(command), "feature-catalog"

    if suffix:
        for motion in SEMANTIC_MOTIONS:
            yield [*motion, *suffix], "motion-plus-original-action"

    before = episode.get("before", {}).get("lines", [])
    after = episode.get("after", {}).get("lines", [])
    if len(before) == len(after) == 1:
        removed = len(str(before[0]).encode()) - len(str(after[0]).encode())
        if 2 <= removed <= 20:
            yield [*str(removed), "x"], "text-delta"

    # Anchored edit templates catch common "walk to boundary, then edit"
    # episodes without attempting an unbounded command search.
    if original_length >= 4:
        for anchor in ("0", "^", "$"):
            for command in DELETE_COMMANDS:
                yield [anchor, *command], "anchor-plus-action"


def generate_local_candidates(episode: dict[str, Any]) -> list[dict[str, Any]]:
    """Return a deterministic, bounded set of strictly shorter programs."""
    original = episode.get("resolvedTokens", [])
    seen: set[tuple[str, ...]] = set()
    generated: list[dict[str, Any]] = []
    for compiled, origin in _programs(episode):
        identity = tuple(compiled)
        if not compiled or identity in seen or compiled == original:
            continue
        if len(compiled) >= len(original) or not token_objects(compiled):
            continue
        seen.add(identity)
        generated.append(_candidate(compiled, origin=origin))
    generated.sort(key=lambda item: (
        -item.get("_rankingPriority", 0),
        len(item.get("compiledTokens", [])),
        "".join(item.get("compiledTokens", [])),
    ))
    return generated[:MAX_LOCAL_CANDIDATES]


def merge_candidates(
    episodes: list[dict[str, Any]], suggestions: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Merge provider proposals with local catalog candidates by episode."""
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
        for candidate in generate_local_candidates(episode):
            if tuple(candidate["compiledTokens"]) not in existing:
                suggestion["candidates"].append(candidate)
                existing.add(tuple(candidate["compiledTokens"]))
    return list(by_id.values())
