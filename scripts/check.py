#!/usr/bin/env python3
"""Run the offline Vim Coach checks used before a demo."""

from __future__ import annotations

from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]


def run(command: list[str]) -> None:
    print("$", " ".join(command))
    subprocess.run(command, cwd=ROOT, check=True)


def main() -> int:
    run([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"])
    run([sys.executable, "replay/verify.py", "tests/fixtures/replay-basic.json"])
    run(["nvim", "--headless", "-u", "demo/minimal.lua", "-i", "NONE", "-n", "+VimCoachStatus", "+qa!"])
    run([
        "nvim", "--headless", "-u", "demo/minimal.lua", "-i", "NONE", "-n",
        "-c", "enew",
        "-c", "call setline(1, ['one two three four'])",
        "-c", "normal! 2wx",
        "-c", "sleep 1200m",
        "-c", "VimCoachPractice",
        "-c", "normal! 2wx",
        "-c", "VimCoachPracticeCheck",
        "-c", "qa!",
    ])
    run([
        "nvim", "--headless", "-u", "demo/minimal.lua", "-i", "NONE", "-n",
        "-c", "enew",
        "-c", "call setline(1, ['abcdef ghi'])",
        "-c", "normal! 0",
        "-c", "sleep 1200m",
        "-c", "normal! llll",
        "-c", "sleep 1200m",
        "-c", "lua assert(require('vim_coach.queue').status().pending == 1, 'navigation episode was not queued')",
        "-c", "qa!",
    ])
    run(["nvim", "--headless", "-u", "demo/suggestion.lua", "-i", "NONE", "-n", "+VimCoachStatus", "+VimCoachDismiss", "+qa!"])
    print("Offline checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
