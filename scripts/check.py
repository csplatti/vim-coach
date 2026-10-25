#!/usr/bin/env python3
"""Run the offline Vim Coach checks used before a demo."""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]


def run(command: list[str]) -> None:
    print("$", " ".join(command))
    if command[0] != "nvim":
        subprocess.run(command, cwd=ROOT, check=True)
        return
    with tempfile.TemporaryDirectory(prefix="vim-coach-check-") as directory:
        environment = os.environ.copy()
        environment["VIM_COACH_HISTORY_FILE"] = str(Path(directory) / "lessons.json")
        environment["VIM_COACH_GOALS_FILE"] = str(Path(directory) / "goals.json")
        subprocess.run(command, cwd=ROOT, check=True, env=environment)


def main() -> int:
    run([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"])
    run([sys.executable, "replay/verify.py", "tests/fixtures/replay-basic.json"])
    run([
        "nvim", "--headless", "-u", "NONE", "-i", "NONE", "-n",
        "-c", "lua dofile('tests/goals_spec.lua')",
        "-c", "qa!",
    ])
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
        "-c", "call setline(1, ['abcdef'])",
        "-c", "normal! vllld",
        "-c", "sleep 1200m",
        "-c", "lua local s=require('vim_coach.queue').status(); assert(s.pending == 1, 'Visual-mode episode was not queued')",
        "-c", "qa!",
    ])
    run([
        "nvim", "--headless", "-u", "demo/minimal.lua", "-i", "NONE", "-n",
        "-c", "enew",
        "-c", "call setline(1, ['alpha'])",
        "-c", 'execute "normal! diwibeta\\<Esc>"',
        "-c", "sleep 1200m",
        "-c", "lua local s=require('vim_coach.queue').status(); assert(s.pending == 1, 'change episode was not queued')",
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
