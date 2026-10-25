#!/usr/bin/env python3
"""Verify original and candidate Vim token sequences in fresh Neovim children."""

from __future__ import annotations

import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
MAX_OUTPUT_BYTES = 32 * 1024
DEFAULT_TIMEOUT_SECONDS = 1.0


def _nvim_executable() -> str:
    """Return the replay executable without mistaking Neovim's server socket for it."""
    return os.environ.get("VIM_COACH_NVIM", "nvim")


def _is_digit(token: Any) -> bool:
    return isinstance(token, str) and len(token) == 1 and token.isdigit()


def validate_tokens(tokens: Any) -> tuple[bool, str]:
    if not isinstance(tokens, list) or not tokens:
        return False, "tokens must be a non-empty array"
    if any(not isinstance(token, str) or len(token) != 1 for token in tokens):
        return False, "tokens must contain one-character strings"

    escape = "\x1b"
    motions = {
        "h", "j", "k", "l", "w", "b", "e", "W", "B", "E", "G",
        "0", "^", "$", "%", "{", "}", "(", ")", ";", ",",
    }
    find_commands = {"f", "F", "t", "T"}
    text_objects = {"w", '"', "(", "{"}

    def literal(token: str) -> bool:
        return token != escape and 32 <= ord(token) <= 126

    def insert_tail(index: int) -> tuple[int | None, str]:
        while index < len(tokens) and tokens[index] != escape:
            if not literal(tokens[index]):
                return None, "insert text contains an unsupported input"
            index += 1
        if index >= len(tokens):
            return None, "insert or change command must end with Escape"
        return index + 1, ""

    def operator_target(index: int) -> tuple[int | None, str]:
        if index >= len(tokens):
            return None, "incomplete operator"
        token = tokens[index]
        if token in {"i", "a"}:
            if index + 1 < len(tokens) and tokens[index + 1] in text_objects:
                return index + 2, ""
            return None, "unsupported text object"
        if token == "g" and index + 1 < len(tokens) and tokens[index + 1] == "g":
            return index + 2, ""
        if token in {"0", "$", "G", "w"}:
            return index + 1, ""
        return None, "unsupported operator target"

    def visual_command(index: int) -> tuple[int | None, str]:
        index += 1
        moved = False
        while index < len(tokens):
            token = tokens[index]
            if token in {"d", "x"} and moved:
                return index + 1, ""
            if token == "c" and moved:
                return insert_tail(index + 1)
            if token in {"i", "a"} and index + 1 < len(tokens) and tokens[index + 1] in text_objects:
                moved = True
                index += 2
                continue
            if token == "g" and index + 1 < len(tokens) and tokens[index + 1] in {"g", "e"}:
                moved = True
                index += 2
                continue
            if token in find_commands and index + 1 < len(tokens) and literal(tokens[index + 1]):
                moved = True
                index += 2
                continue
            if token != "0" and token in set("123456789"):
                count = 0
                while index < len(tokens) and _is_digit(tokens[index]):
                    count = count * 10 + int(tokens[index])
                    index += 1
                if count > 20:
                    return None, "count exceeds the supported limit of 20"
                if index >= len(tokens):
                    return None, "incomplete Visual-mode count"
                token = tokens[index]
            if token == "0" or token in motions - {"0"}:
                moved = True
                index += 1
                continue
            return None, "unsupported Visual-mode sequence"
        return None, "incomplete Visual-mode command"

    index = 0
    while index < len(tokens):
        if tokens[index] != "0" and tokens[index] in set("123456789"):
            count = 0
            while index < len(tokens) and _is_digit(tokens[index]):
                count = count * 10 + int(tokens[index])
                index += 1
            if count > 20:
                return False, "count exceeds the supported limit of 20"
        if index >= len(tokens):
            return False, "incomplete count or command"

        token = tokens[index]
        if token in {"v", "V"}:
            index, reason = visual_command(index)
            if index is None:
                return False, reason
            continue
        if token == "0" or token in motions - {"0"}:
            index += 1
            continue
        if token == "g":
            if index + 1 < len(tokens) and tokens[index + 1] in {"g", "e"}:
                index += 2
                continue
            return False, "unsupported g motion"
        if token in find_commands:
            if index + 1 < len(tokens) and literal(tokens[index + 1]):
                index += 2
                continue
            return False, "find motion requires one printable target"
        if token in {"x", "D"}:
            index += 1
            continue
        if token == "r":
            if index + 1 < len(tokens) and literal(tokens[index + 1]):
                index += 2
                continue
            return False, "replace requires one printable character"
        if token in {"i", "a", "C"}:
            index, reason = insert_tail(index + 1)
            if index is None:
                return False, reason
            continue
        if token not in {"d", "c"}:
            return False, "unsupported command sequence"
        if token == "d" and index + 1 < len(tokens) and tokens[index + 1] == "d":
            index += 2
            continue
        target_end, reason = operator_target(index + 1)
        if target_end is None:
            return False, reason
        if token == "c":
            index, reason = insert_tail(target_end)
            if index is None:
                return False, reason
        else:
            index = target_end

    return True, ""


def _run_child(before: dict[str, Any], tokens: list[str], timeout: float) -> dict[str, Any]:
    payload = {"schemaVersion": 1, "before": before, "tokens": tokens}
    command = [
        _nvim_executable(),
        "--headless",
        "-u",
        "NONE",
        "-i",
        "NONE",
        "-n",
        "--noplugin",
        "-c",
        "lua dofile('replay/runner.lua')",
    ]
    child_env = {**os.environ, "TMPDIR": "/private/tmp"}
    child_env.pop("NVIM", None)
    child_env.pop("NVIM_LISTEN_ADDRESS", None)
    process = subprocess.Popen(
        command,
        cwd=ROOT,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        start_new_session=True,
        env=child_env,
    )
    try:
        stdout, stderr = process.communicate(
            json.dumps(payload, separators=(",", ":")).encode("utf-8"),
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as error:
        os.killpg(process.pid, signal.SIGKILL)
        process.wait()
        raise RuntimeError("replay child timed out") from error

    if len(stdout) + len(stderr) > MAX_OUTPUT_BYTES:
        raise RuntimeError("replay child exceeded the output limit")
    if process.returncode != 0:
        detail = stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(detail or f"replay child exited with {process.returncode}")

    lines = [line for line in stdout.decode("utf-8", errors="replace").splitlines() if line.strip()]
    if not lines:
        raise RuntimeError("replay child returned no JSON")
    try:
        result = json.loads(lines[-1])
    except json.JSONDecodeError as error:
        raise RuntimeError("replay child returned malformed JSON") from error
    if not result.get("ok"):
        raise RuntimeError(result.get("error", "replay child rejected the input"))
    return result["state"]


def _state_projection(state: dict[str, Any]) -> dict[str, Any]:
    return {
        "lines": state.get("lines"),
        "finalNewline": state.get("finalNewline"),
        "cursor": state.get("cursor"),
        "mode": state.get("mode"),
        "trackedRegisters": state.get("trackedRegisters"),
    }


def _verification_result(
    expected_after: dict[str, Any],
    original_state: dict[str, Any],
    candidate_state: dict[str, Any],
    original: list[str],
    candidate: list[str],
    original_latency_ms: float,
    candidate_latency_ms: float,
    require_register_equality: bool,
) -> dict[str, Any]:
    expected_projection = _state_projection(expected_after)
    original_projection = _state_projection(original_state)
    candidate_projection = _state_projection(candidate_state)
    primary_fields = ("lines", "finalNewline", "cursor", "mode")
    original_mismatch_fields = [
        key for key in primary_fields if original_projection.get(key) != expected_projection.get(key)
    ]
    candidate_mismatch_fields = [
        key for key in primary_fields if candidate_projection.get(key) != expected_projection.get(key)
    ]
    # Register snapshots captured in the live editor are not reliably
    # reconstructible in a fresh child because restoring numbered registers can
    # itself alter register state. Compare candidate side effects with the
    # original replay instead; both runs start from the same reconstructed state.
    registers_equal = candidate_projection.get("trackedRegisters") == original_projection.get("trackedRegisters")
    if require_register_equality and not registers_equal:
        candidate_mismatch_fields.append("trackedRegisters")
    original_matches = not original_mismatch_fields
    candidate_matches = not candidate_mismatch_fields
    original_count = len(original)
    candidate_count = len(candidate)
    saved = original_count - candidate_count

    reason = None
    if not original_matches:
        reason = "original replay did not reproduce the captured target"
    elif not candidate_matches:
        reason = "candidate replay did not reproduce the captured target"
    elif saved <= 0:
        reason = "candidate is not strictly shorter"

    return {
        "schemaVersion": 1,
        "accepted": reason is None,
        "originalReplayMatches": original_matches,
        "candidateReplayMatches": candidate_matches,
        "registersEqual": registers_equal,
        "comparisonPolicy": "full-state" if require_register_equality else "editing-outcome",
        "originalMismatchFields": original_mismatch_fields,
        "candidateMismatchFields": candidate_mismatch_fields,
        "originalLogicalKeys": original_count,
        "candidateLogicalKeys": candidate_count,
        "savedLogicalKeys": saved,
        "rejectionReason": reason,
        "originalReplayLatencyMs": original_latency_ms,
        "candidateReplayLatencyMs": candidate_latency_ms,
    }


def verify_many(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Verify many candidates while replaying the original only once."""
    if payload.get("schemaVersion") != 1:
        raise ValueError("unsupported schema version")
    before = payload.get("before")
    expected_after = payload.get("after")
    original = payload.get("originalTokens")
    candidates = payload.get("candidateTokenSets")
    require_register_equality = payload.get("requireRegisterEquality", True) is not False
    if not isinstance(before, dict) or not isinstance(expected_after, dict):
        raise ValueError("before and after snapshots are required")
    valid, reason = validate_tokens(original)
    if not valid:
        raise ValueError(f"originalTokens: {reason}")
    if not isinstance(candidates, list):
        raise ValueError("candidateTokenSets must be an array")
    for index, candidate in enumerate(candidates):
        valid, reason = validate_tokens(candidate)
        if not valid:
            raise ValueError(f"candidateTokenSets[{index}]: {reason}")

    started = time.monotonic()
    original_state = _run_child(before, original, DEFAULT_TIMEOUT_SECONDS)
    original_latency_ms = round((time.monotonic() - started) * 1000, 2)
    results = []
    for candidate in candidates:
        started = time.monotonic()
        candidate_state = _run_child(before, candidate, DEFAULT_TIMEOUT_SECONDS)
        candidate_latency_ms = round((time.monotonic() - started) * 1000, 2)
        results.append(_verification_result(
            expected_after,
            original_state,
            candidate_state,
            original,
            candidate,
            original_latency_ms,
            candidate_latency_ms,
            require_register_equality,
        ))
    return results


def verify(payload: dict[str, Any]) -> dict[str, Any]:
    candidate = payload.get("candidateTokens")
    results = verify_many({
        **payload,
        "candidateTokenSets": [candidate],
    })
    return results[0]


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(f"usage: {argv[0]} PAYLOAD.json", file=sys.stderr)
        return 2
    try:
        payload = json.loads(Path(argv[1]).read_text(encoding="utf-8"))
        result = verify(payload)
    except (OSError, json.JSONDecodeError, ValueError, RuntimeError) as error:
        print(json.dumps({"accepted": False, "error": str(error)}))
        return 2
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
