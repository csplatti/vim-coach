#!/usr/bin/env python3
"""Run a live, replay-verified coverage evaluation against the configured model."""

from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from replay.verify import _run_child
from scripts.provider_diagnostic import load_env_file
from worker.orchestrator import augment_local_candidates, verify_batch_candidates
from worker.provider import LLMClient, LLMConfig
from worker.vim_help import add_help_lessons


SCENARIOS = [
    ("end-of-word", "navigation", "alpha beta", 0, list("llll"), ["e"]),
    ("next-word", "navigation", "abc def", 0, list("llll"), ["w"]),
    ("previous-word", "navigation", "abc def", 4, list("hhhh"), ["b"]),
    ("end-of-line", "navigation", "abcdef", 0, list("lllll"), ["$"]),
    ("start-of-line", "navigation", "abcdef", 5, list("hhhhh"), ["0"]),
    ("first-nonblank", "navigation", "    alpha", 8, list("hhhh"), ["^"]),
    ("counted-columns", "navigation", "abcdefghijkl", 0, list("llllllll"), ["8", "l"]),
    ("counted-words", "navigation", "one two three four", 0, list("www"), ["3", "w"]),
    ("word-end-delete", "edit", "alpha beta", 0, list("llllx"), ["e", "x"]),
    ("counted-word-delete", "edit", "one two three four", 0, list("wwwx"), ["3", "w", "x"]),
    ("position-then-count", "edit", "one two three four", 17, list("0wwwx"), ["0", "3", "w", "x"]),
    ("cancelled-motion-delete", "edit", "abc", 0, list("lhx"), ["x"]),
    ("delete-to-end", "edit", "abcdef", 2, list("xxxx"), ["D"]),
    ("delete-inner-word", "edit", "alpha beta", 0, list("xxxxx"), ["d", "i", "w"]),
    ("jump-first-line", "navigation", ["one", "two", "three", "four", "five", "six"], (6, 0), list("kkkkk"), ["g", "g"]),
    ("jump-last-line", "navigation", ["one", "two", "three", "four", "five", "six"], (1, 0), list("jjjjj"), ["G"]),
    ("next-WORD", "navigation", "foo.bar baz", 0, list("www"), ["W"]),
    ("previous-WORD", "navigation", "foo.bar baz", 8, list("bbb"), ["B"]),
    ("end-WORD", "navigation", "foo.bar baz", 0, list("llllll"), ["E"]),
    ("previous-word-end", "navigation", "abc    def", 7, list("hhhhh"), ["g", "e"]),
    ("matching-pair", "navigation", "(abc)", 0, list("llll"), ["%"]),
]


def make_episode(identifier: int, scenario: tuple[Any, ...]) -> dict[str, Any]:
    name, kind, text, position, original, expected = scenario
    lines = text if isinstance(text, list) else [text]
    row, column = position if isinstance(position, tuple) else (1, position)
    before = {
        "lines": lines,
        "finalNewline": True,
        "cursor": {"row1Based": row, "byteColumn0Based": column},
        "mode": "n",
        "trackedRegisters": {},
    }
    after = _run_child(before, original, 1.0)
    expected_after = _run_child(before, expected, 1.0)
    for field in ("lines", "finalNewline", "cursor", "mode"):
        if expected_after.get(field) != after.get(field):
            raise RuntimeError(f"invalid evaluation scenario {name}: expected candidate differs in {field}")
    return {
        "id": identifier,
        "kind": kind,
        "name": name,
        "expectedCandidate": expected,
        "before": before,
        "after": after,
        "resolvedTokens": original,
    }


def main() -> int:
    load_env_file(ROOT / ".env")
    episodes = [make_episode(index, scenario) for index, scenario in enumerate(SCENARIOS, 1)]
    client = LLMClient(LLMConfig.from_env(cloud_enabled=True))
    proposed = client.propose_batch(episodes, [])
    diagnostics: list[dict[str, Any]] = []
    candidates_to_verify = augment_local_candidates(episodes, proposed["suggestions"])
    verified = add_help_lessons(
        verify_batch_candidates(episodes, candidates_to_verify, diagnostics)
    )

    proposed_by_id = {
        item["episodeId"]: [candidate["compiledTokens"] for candidate in item.get("candidates", [])]
        for item in proposed["suggestions"]
    }
    verified_by_id = {
        item["episodeId"]: item.get("candidates", [])
        for item in verified
    }
    rejected_by_id: dict[int, list[dict[str, Any]]] = {}
    for item in diagnostics:
        rejected_by_id.setdefault(item.get("episodeId"), []).append(item)

    passed = 0
    rows = []
    for episode in episodes:
        candidates = verified_by_id.get(episode["id"], [])
        verified_tokens = [candidate["compiledTokens"] for candidate in candidates]
        target_hit = episode["expectedCandidate"] in verified_tokens
        if target_hit:
            passed += 1
        rows.append({
            "scenario": episode["name"],
            "kind": episode["kind"],
            "original": "".join(episode["resolvedTokens"]),
            "expected": "".join(episode["expectedCandidate"]),
            "proposed": ["".join(tokens) for tokens in proposed_by_id.get(episode["id"], [])],
            "verified": ["".join(tokens) for tokens in verified_tokens],
            "helpTags": [candidate.get("helpTag") for candidate in candidates],
            "targetHit": target_hit,
            "rejections": [item.get("reason") for item in rejected_by_id.get(episode["id"], [])],
        })

    print(json.dumps({
        "model": proposed["model"],
        "scenarios": len(episodes),
        "expectedTargetsVerified": passed,
        "coveragePercent": round(100 * passed / len(episodes), 1),
        "results": rows,
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
