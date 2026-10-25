"""Generate bounded, replay-safe candidates from the supported Vim catalog.

These are possibilities, not recommendations. The replay verifier remains the
authority on whether a candidate reaches the captured target.
"""

from __future__ import annotations

import re
from typing import Any, Iterable

from worker.contracts import CHANGE_COMMANDS, DELETE_COMMANDS, FIND_COMMANDS

ESC = "\x1b"
SEMANTIC_MOTIONS = (
    "w", "b", "e", "W", "B", "E", "ge", "gg", "G", "0", "^", "$", "%",
    "{", "}", "(", ")",
)
COUNTABLE_MOTIONS = {"h", "j", "k", "l", "w", "b", "e", "W", "B", "E"}
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
    "W": 77,
    "B": 77,
    "E": 77,
    "ge": 72,
    "w": 78,
    "b": 78,
    "e": 78,
    "count": 55,
    "x": 40,
    "f": 82, "F": 82, "t": 80, "T": 80,
    "{": 76, "}": 76, "(": 74, ")": 74,
    'di"': 96, 'da"': 95, "di(": 94, "da(": 93, "di{": 94, "da{": 93,
    "d$": 92, "d0": 88, "dG": 90, "dgg": 90,
    "ciw": 98, 'ci"': 98, 'ca"': 97, "ci(": 97, "ca(": 96,
    "ci{": 97, "ca{": 96, "cw": 90, "C": 92, "r": 90,
}
MAX_LOCAL_CANDIDATES = 64


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
        if value in {"h", "j", "k", "l", "w", "b", "e", "W", "B", "E", "G", "0", "^", "$", "%", "{", "}", "(", ")", ";", ","}:
            tokens.append({"kind": "move", "key": value})
            index += 1
            continue
        if value in FIND_COMMANDS and index + 1 < len(compiled):
            tokens.append({"kind": "find", "command": value, "target": compiled[index + 1]})
            index += 2
            continue
        if value == "r" and index + 1 < len(compiled):
            tokens.append({"kind": "replace", "target": compiled[index + 1]})
            index += 2
            continue
        change = next((
            command for command in sorted(CHANGE_COMMANDS, key=len, reverse=True)
            if compiled[index:index + len(command)] == list(command)
        ), None)
        if change is not None and compiled and compiled[-1] == ESC:
            text_start = index + len(change)
            tokens.append({"kind": "change", "command": change, "text": "".join(compiled[text_start:-1])})
            index = len(compiled)
            continue
        command = next((
            command for command in sorted(DELETE_COMMANDS, key=len, reverse=True)
            if compiled[index:index + len(command)] == list(command)
        ), None)
        if command is not None:
            tokens.append({"kind": "delete", "command": command})
            index += len(command)
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
    for width in range(3, 0, -1):
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
        if token.get("kind") == "find":
            return str(token.get("command"))
        if token.get("kind") == "change":
            return str(token.get("command"))
        if token.get("kind") == "replace":
            return "r"
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


def _find_motion_programs(episode: dict[str, Any]) -> Iterable[list[str]]:
    before = episode.get("before", {})
    lines = before.get("lines", [])
    after_row, after_col = _cursor(episode.get("after", {}))
    if not isinstance(lines, list) or not 1 <= after_row <= len(lines):
        return
    line = lines[after_row - 1]
    if not isinstance(line, str) or not line.isascii():
        return
    targets = {
        "f": after_col,
        "F": after_col,
        "t": after_col + 1,
        "T": after_col - 1,
    }
    for command, column in targets.items():
        if 0 <= column < len(line) and 32 <= ord(line[column]) <= 126:
            yield [command, line[column]]


def _replacement_texts(episode: dict[str, Any]) -> list[str]:
    before = episode.get("before", {}).get("lines", [])
    after = episode.get("after", {}).get("lines", [])
    if not (isinstance(before, list) and isinstance(after, list) and len(before) == len(after) == 1):
        return []
    left, right = before[0], after[0]
    if not isinstance(left, str) or not isinstance(right, str) or not left.isascii() or not right.isascii():
        return []
    prefix = 0
    while prefix < min(len(left), len(right)) and left[prefix] == right[prefix]:
        prefix += 1
    suffix = 0
    while (
        suffix < len(left) - prefix
        and suffix < len(right) - prefix
        and left[-1 - suffix] == right[-1 - suffix]
    ):
        suffix += 1
    inserted = right[prefix:len(right) - suffix if suffix else len(right)]
    values = {inserted}
    if len(right) <= 64:
        values.add(right)
    _, after_col = _cursor(episode.get("after", {}))
    for match in re.finditer(r"[A-Za-z0-9_]+", right):
        if match.start() <= after_col <= match.end():
            values.add(match.group(0))
    return sorted(
        value for value in values
        if value and len(value) <= 64 and all(32 <= ord(character) <= 126 for character in value)
    )


def _programs(episode: dict[str, Any]) -> Iterable[tuple[list[str], str]]:
    original = episode.get("resolvedTokens", [])
    compressed = _compressed_motion_candidate(original)
    if compressed:
        yield compressed, "count-compression"

    if episode.get("kind") == "navigation":
        targeted = _targeted_motion(episode)
        if targeted:
            yield targeted, "cursor-delta"
        for motion in SEMANTIC_MOTIONS:
            yield list(motion), "feature-catalog"
        for motion in _find_motion_programs(episode):
            yield motion, "find-target"
        return

    suffix = _delete_suffix(original)
    for command in sorted(DELETE_COMMANDS):
        yield list(command), "feature-catalog"

    if suffix:
        for motion in SEMANTIC_MOTIONS:
            yield [*motion, *suffix], "motion-plus-original-action"
        for motion in _find_motion_programs(episode):
            yield [*motion, *suffix], "find-plus-original-action"

    before = episode.get("before", {}).get("lines", [])
    after = episode.get("after", {}).get("lines", [])
    if len(before) == len(after) == 1:
        removed = len(str(before[0]).encode()) - len(str(after[0]).encode())
        if 2 <= removed <= 20:
            yield [*str(removed), "x"], "text-delta"
    elif isinstance(before, list) and isinstance(after, list):
        removed_lines = len(before) - len(after)
        if 2 <= removed_lines <= 20:
            yield [*str(removed_lines), "d", "d"], "line-delta"

    for replacement in _replacement_texts(episode):
        for command in sorted(CHANGE_COMMANDS):
            yield [*command, *replacement, ESC], "change-template"

    if len(before) == len(after) == 1 and len(before[0]) == len(after[0]):
        differences = [
            index for index, (left, right) in enumerate(zip(before[0], after[0]))
            if left != right
        ]
        if len(differences) == 1:
            target = after[0][differences[0]]
            if target.isascii() and 32 <= ord(target) <= 126:
                yield ["r", target], "single-character-replace"


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
