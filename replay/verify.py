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


def _is_digit(token: Any) -> bool:
    return isinstance(token, str) and len(token) == 1 and token.isdigit()


def validate_tokens(tokens: Any) -> tuple[bool, str]:
    if not isinstance(tokens, list) or not tokens:
        return False, "tokens must be a non-empty array"
    if any(not isinstance(token, str) or len(token) != 1 for token in tokens):
        return False, "tokens must contain one-character strings"

    motions = {"h", "l", "w", "b", "e", "0", "^", "$"}
    supported = motions | {"x", "D", "d", "i", "a"} | set("123456789")
    if any(token not in supported for token in tokens):
        return False, "token is outside the supported grammar"

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
        if token == "0" or token in motions - {"0"} or token in {"x", "D"}:
            index += 1
            continue
        if token != "d":
            return False, "unsupported command sequence"

        if index + 1 >= len(tokens):
            return False, "incomplete delete operator"
        operator = tokens[index + 1]
        if operator in {"d", "w"}:
            index += 2
        elif operator in {"i", "a"} and index + 2 < len(tokens) and tokens[index + 2] == "w":
            index += 3
        else:
            return False, "unsupported delete command"

    return True, ""


def _run_child(before: dict[str, Any], tokens: list[str], timeout: float) -> dict[str, Any]:
    payload = {"schemaVersion": 1, "before": before, "tokens": tokens}
    command = [
        os.environ.get("NVIM", "nvim"),
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
    process = subprocess.Popen(
        command,
        cwd=ROOT,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        start_new_session=True,
        env={**os.environ, "TMPDIR": "/private/tmp"},
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


def verify(payload: dict[str, Any]) -> dict[str, Any]:
    if payload.get("schemaVersion") != 1:
        raise ValueError("unsupported schema version")
    before = payload.get("before")
    expected_after = payload.get("after")
    original = payload.get("originalTokens")
    candidate = payload.get("candidateTokens")
    if not isinstance(before, dict) or not isinstance(expected_after, dict):
        raise ValueError("before and after snapshots are required")

    for label, tokens in (("originalTokens", original), ("candidateTokens", candidate)):
        valid, reason = validate_tokens(tokens)
        if not valid:
            raise ValueError(f"{label}: {reason}")

    started = time.monotonic()
    original_state = _run_child(before, original, DEFAULT_TIMEOUT_SECONDS)
    original_latency_ms = round((time.monotonic() - started) * 1000, 2)

    started = time.monotonic()
    candidate_state = _run_child(before, candidate, DEFAULT_TIMEOUT_SECONDS)
    candidate_latency_ms = round((time.monotonic() - started) * 1000, 2)

    original_matches = _state_projection(original_state) == _state_projection(expected_after)
    candidate_matches = _state_projection(candidate_state) == _state_projection(expected_after)
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
        "originalLogicalKeys": original_count,
        "candidateLogicalKeys": candidate_count,
        "savedLogicalKeys": saved,
        "rejectionReason": reason,
        "originalReplayLatencyMs": original_latency_ms,
        "candidateReplayLatencyMs": candidate_latency_ms,
    }


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
