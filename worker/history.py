"""Small local JSON history for verified lesson metadata.

Raw buffer snapshots are intentionally not written here. Neovim can
use this metadata for its inbox, while practice examples remain an explicit
future opt-in.
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
from typing import Any


HISTORY_SCHEMA_VERSION = 1
MAX_HISTORY_ITEMS = 500


def _lesson_identity(lesson: dict[str, Any]) -> str:
    help_tag = lesson.get("helpTag")
    if isinstance(help_tag, str) and help_tag:
        return "help:" + help_tag
    concept = lesson.get("concept")
    if isinstance(concept, str) and concept:
        return "concept:" + concept.strip().lower()
    tokens = lesson.get("compiledTokens", [])
    return "tokens:" + "".join(tokens if isinstance(tokens, list) else [])


def history_path() -> Path:
    configured = os.environ.get("VIM_COACH_HISTORY_FILE")
    if configured:
        return Path(configured).expanduser()
    return Path.home() / ".local" / "state" / "vim-coach" / "lessons.json"


def _read(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    value = json.loads(path.read_text())
    if not isinstance(value, dict) or value.get("schemaVersion") != HISTORY_SCHEMA_VERSION:
        return []
    lessons = value.get("lessons", [])
    return lessons if isinstance(lessons, list) else []


def _write(path: Path, lessons: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps({
        "schemaVersion": HISTORY_SCHEMA_VERSION,
        "lessons": lessons,
    }, indent=2) + "\n")
    temporary.replace(path)


def append_verified_lessons(
    path: Path,
    suggestions: list[dict[str, Any]],
    model: str,
    *,
    created_at: str | None = None,
) -> int:
    timestamp = created_at or datetime.now(timezone.utc).isoformat()
    lessons = _read(path)
    known_lessons = {_lesson_identity(lesson) for lesson in lessons}
    added = 0
    for suggestion in suggestions:
        for index, candidate in enumerate(suggestion.get("candidates", [])):
            lesson = {
                "lessonId": f"{suggestion.get('episodeId')}-{timestamp}-{index}",
                "episodeId": suggestion.get("episodeId"),
                "model": model,
                "createdAt": timestamp,
                "tokens": candidate.get("tokens", []),
                "originalTokens": candidate.get("originalTokens", []),
                "compiledTokens": candidate.get("compiledTokens", []),
                "concept": candidate.get("concept", ""),
                "explanation": candidate.get("explanation", ""),
                "helpTag": candidate.get("helpTag"),
                "featureKey": candidate.get("_featureKey"),
                "documentationSource": candidate.get("documentationSource"),
                "originalLogicalKeys": candidate.get("originalLogicalKeys"),
                "candidateLogicalKeys": candidate.get("candidateLogicalKeys"),
                "savedLogicalKeys": candidate.get("savedLogicalKeys"),
                "verification": candidate.get("verification", {}),
                "status": "new",
            }
            identity = _lesson_identity(lesson)
            if identity in known_lessons:
                continue
            lessons.append(lesson)
            known_lessons.add(identity)
            added += 1
    lessons = lessons[-MAX_HISTORY_ITEMS:]
    _write(path, lessons)
    return added


def update_lesson_status(path: Path, lesson_id: str, status: str) -> bool:
    if status not in {"new", "dismissed", "known"}:
        raise ValueError("unsupported lesson status")
    lessons = _read(path)
    found = False
    for lesson in lessons:
        if lesson.get("lessonId") == lesson_id:
            lesson["status"] = status
            lesson["updatedAt"] = datetime.now(timezone.utc).isoformat()
            found = True
            break
    if found:
        _write(path, lessons)
    return found


def reset_lesson_statuses(path: Path) -> int:
    lessons = _read(path)
    changed = 0
    for lesson in lessons:
        if lesson.get("status") != "new":
            lesson["status"] = "new"
            changed += 1
    if changed:
        _write(path, lessons)
    return changed


def related_lessons(
    path: Path,
    episodes: list[dict[str, Any]],
    *,
    limit: int = 8,
) -> list[dict[str, Any]]:
    """Return small metadata-only retrieval context for a new batch."""
    query_tokens = {
        token
        for episode in episodes
        for token in episode.get("resolvedTokens", [])
        if isinstance(token, str)
    }
    scored: list[tuple[int, int, dict[str, Any]]] = []
    lessons = _read(path)
    for index, lesson in enumerate(lessons):
        candidate_tokens = {
            token
            for token in lesson.get("compiledTokens", [])
            if isinstance(token, str)
        }
        score = len(query_tokens & candidate_tokens)
        if score == 0 and lesson.get("status") != "new":
            continue
        scored.append((score, index, {
            "concept": lesson.get("concept", ""),
            "helpTag": lesson.get("helpTag"),
            "explanation": lesson.get("explanation", ""),
            "compiledTokens": lesson.get("compiledTokens", []),
            "savedLogicalKeys": lesson.get("savedLogicalKeys"),
            "status": lesson.get("status", "new"),
        }))
    scored.sort(key=lambda item: (-item[0], -item[1]))
    return [item[2] for item in scored[:limit]]


def lesson_profile(path: Path) -> dict[str, dict[str, Any]]:
    """Summarize prior feature exposure without retaining source snapshots."""
    help_aliases = {"d": "dw", "iw": "diw", "aw": "daw"}
    profile: dict[str, dict[str, Any]] = {}
    for lesson in _read(path):
        feature = lesson.get("featureKey")
        if not isinstance(feature, str) or not feature:
            help_tag = lesson.get("helpTag")
            feature = help_aliases.get(help_tag, help_tag) if isinstance(help_tag, str) else None
        if not isinstance(feature, str) or not feature:
            continue
        item = profile.setdefault(feature, {
            "exposures": 0,
            "known": False,
            "dismissals": 0,
        })
        item["exposures"] += 1
        status = lesson.get("status", "new")
        if status == "known":
            item["known"] = True
        elif status == "dismissed":
            item["dismissals"] += 1
    return profile
