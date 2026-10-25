"""Turn verified candidate tokens into concise, local Neovim help lessons."""

from __future__ import annotations

import os
from pathlib import Path
import re
import subprocess
from typing import Any


FEATURES: dict[str, tuple[str, str, str]] = {
    "count": ("Counts", "count", r"^\[count\]\s+"),
    "h": ("Move left", "h", r"^h\s+"),
    "j": ("Move down", "j", r"^j\s+"),
    "k": ("Move up", "k", r"^k\s+"),
    "l": ("Move right", "l", r"^l\s+"),
    "w": ("Move by words", "w", r"^w\s+"),
    "b": ("Move backward by words", "b", r"^b\s+"),
    "e": ("Move to the end of a word", "e", r"^e\s+"),
    "W": ("Move by whitespace-separated WORDS", "W", r"^W\s+"),
    "B": ("Move backward by WORDS", "B", r"^B\s+"),
    "E": ("Move to the end of a WORD", "E", r"^E\s+"),
    "ge": ("Move to the previous word end", "ge", r"^ge\s+"),
    "gg": ("Jump to the first line", "gg", r"^gg\s+"),
    "G": ("Jump to the last line", "G", r"^G\s+"),
    "0": ("Move to the start of a line", "0", r"^0\s+"),
    "^": ("Move to the first non-blank character", "^", r"^\^\s+"),
    "$": ("Move to the end of a line", "$", r"^\$\s+"),
    "%": ("Jump to a matching pair", "%", r"^%\s+"),
    "x": ("Delete characters", "x", r'^\["x\]x\s+'),
    "D": ("Delete to the end of a line", "D", r'^\["x\]D\s+'),
    "dd": ("Delete lines", "dd", r'^\["x\]dd\s+'),
    "dw": ("Delete with a motion", "d", r'^\["x\]d\{motion\}\s+'),
    "diw": ("Delete inside a word", "iw", r"^iw\s+"),
    "daw": ("Delete around a word", "aw", r"^aw\s+"),
}


def _runtime_path() -> Path | None:
    configured = os.environ.get("VIMRUNTIME")
    if configured:
        path = Path(configured)
        if path.is_dir():
            return path
    try:
        result = subprocess.run(
            ["nvim", "--headless", "-u", "NONE", "-i", "NONE", "-n", "--cmd", "lua io.write(vim.env.VIMRUNTIME)", "+qa"],
            check=True,
            capture_output=True,
            text=True,
            timeout=2,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    path = Path(result.stdout.strip())
    return path if path.is_dir() else None


def _clean_help_text(value: str) -> str:
    value = re.sub(r"\*[^*]+\*", "", value)
    value = re.sub(r"\|([^|]+)\|", r"\1", value)
    return " ".join(value.split())


def help_summary(tag: str, prefix_pattern: str, runtime: Path | None = None) -> str:
    runtime = runtime or _runtime_path()
    fallback = f"Open Neovim's built-in documentation with :help {tag}."
    if runtime is None:
        return fallback
    tags_path = runtime / "doc" / "tags"
    try:
        tag_line = next(
            line for line in tags_path.read_text(encoding="utf-8").splitlines()
            if line.startswith(tag + "\t")
        )
        _, filename, _ = tag_line.split("\t", 2)
        lines = (runtime / "doc" / filename).read_text(encoding="utf-8").splitlines()
    except (OSError, StopIteration, ValueError):
        return fallback

    marker = f"*{tag}*"
    marker_index = next((index for index, line in enumerate(lines) if marker in line), None)
    if marker_index is None:
        return fallback
    prefix = re.compile(prefix_pattern)
    for index in range(marker_index, min(len(lines), marker_index + 16)):
        cleaned = _clean_help_text(lines[index])
        if not prefix.search(cleaned):
            continue
        collected = [prefix.sub("", cleaned, count=1)]
        while not re.search(r"[.!?](?:\s|$)", " ".join(collected)) and index + 1 < len(lines):
            index += 1
            continuation = _clean_help_text(lines[index])
            if not continuation:
                break
            collected.append(continuation)
        summary = " ".join(collected)
        sentence = re.split(r"(?<=[.!?])\s", summary, maxsplit=1)[0]
        return sentence[:240]
    return fallback


def feature_catalog(runtime: Path | None = None) -> list[dict[str, Any]]:
    runtime = runtime or _runtime_path()
    catalog = []
    for key, (title, tag, prefix) in FEATURES.items():
        if key == "count":
            token = {"kind": "count", "value": "1-20"}
        elif key in {"h", "j", "k", "l", "w", "b", "e", "W", "B", "E", "ge", "gg", "G", "0", "^", "$", "%"}:
            token = {"kind": "move", "key": key}
        else:
            token = {"kind": "delete", "command": key}
        catalog.append({
            "helpTag": tag,
            "title": title,
            "token": token,
            "documentation": help_summary(tag, prefix, runtime),
        })
    return catalog


def _feature_key(candidate: dict[str, Any]) -> str | None:
    tokens = candidate.get("tokens", [])
    original_tokens = set(candidate.get("originalTokens", []))
    if any(token.get("kind") == "count" for token in tokens if isinstance(token, dict)):
        if not any(isinstance(token, str) and token.isdigit() for token in original_tokens):
            return "count"
    for token in tokens:
        if (
            isinstance(token, dict)
            and token.get("kind") == "move"
            and token.get("key") not in original_tokens
        ):
            return token.get("key")
    for token in tokens:
        if (
            isinstance(token, dict)
            and token.get("kind") == "delete"
            and token.get("command") not in original_tokens
        ):
            return token.get("command")
    if any(token.get("kind") == "count" for token in tokens if isinstance(token, dict)):
        return "count"
    for token in tokens:
        if isinstance(token, dict) and token.get("kind") == "move":
            return token.get("key")
    for token in tokens:
        if isinstance(token, dict) and token.get("kind") == "delete":
            return token.get("command")
    return None


def add_help_lessons(suggestions: list[dict[str, Any]], runtime: Path | None = None) -> list[dict[str, Any]]:
    enriched: list[dict[str, Any]] = []
    for suggestion in suggestions:
        candidates = []
        for candidate in suggestion.get("candidates", []):
            feature = FEATURES.get(_feature_key(candidate) or "")
            if feature is None:
                continue
            title, tag, prefix = feature
            candidates.append({
                **candidate,
                "concept": title,
                "explanation": help_summary(tag, prefix, runtime),
                "helpTag": tag,
                "documentationSource": "nvim-runtime-help",
            })
        enriched.append({**suggestion, "candidates": candidates})
    return enriched
