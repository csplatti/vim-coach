# Vim Coach

Vim Coach is a native Neovim plugin that watches supported editing and cursor
movement sequences, finds shorter Vim alternatives, verifies them in a clean
Neovim replay, and turns new techniques into learning goals.

It stays out of the way while you work. A completed sequence is analyzed
automatically. If another sequence is captured while analysis is running, it
waits in a bounded queue and is included in the next batch.

## What it does

- Captures bounded Normal, Insert, and supported Visual-mode episodes.
- Coaches inefficient edits and repeated cursor movements.
- Generates candidates from a curated local Vim catalog and, optionally, a
  Modal-hosted language model.
- Rejects candidates unless replay reproduces the captured text, cursor,
  final-newline state, and Normal mode.
- Uses concise documentation from the installed Neovim runtime for lessons.
- Avoids duplicate lessons by tracking concepts already introduced.
- Creates practice goals and counts successful uses of learned bindings.
- Stores lesson and goal metadata locally without persisting source snapshots.

The supported catalog currently contains 54 replay-supported topics covering
counts; word, line, file, pair, sentence, and paragraph motions; character
finds; common text objects; bounded delete and change operations; and
single-character replacement. It is intentionally a safe subset of Vim, not
complete Vim emulation.

## Requirements

- Neovim 0.9.4 or newer
- Python 3
- The Python packages in `requirements.txt`
- Optional: a Modal OpenAI-compatible endpoint and proxy token

Create the worker environment from the repository root:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

On an Apple Silicon machine running an x86_64 Neovim under Rosetta, create the
matching environment instead:

```sh
arch -x86_64 python3 -m venv .venv-x86
arch -x86_64 .venv-x86/bin/python -m pip install -r requirements.txt
```

Vim Coach automatically prefers `.venv-x86`, then `.venv`, and otherwise
falls back to `python3`.

## Install with NvChad or lazy.nvim

Add the checkout as a local plugin. For this NvChad setup, place the following
in `lua/custom/plugins.lua`, replacing the path with your checkout:

```lua
{
  dir = "/absolute/path/to/vim-coach",
  name = "vim-coach",
  lazy = false,
  config = function()
    require("vim_coach").setup({
      enabled = true,
      cloud_enabled = true,
      idle_ms = 250,
      goal_target = 10,
    })
  end,
}
```

This is also a valid local lazy.nvim plugin specification. Restart Neovim
after adding it. Vim Coach then loads during an ordinary launch—no custom
`nvim -u ...` command or repository working directory is required.

Confirm the installation with:

```vim
:VimCoachStatus
```

## Provider configuration

Vim Coach can combine its local candidate catalog with contextual suggestions
from a Modal endpoint. Copy the example environment file:

```sh
cp .env.example .env
```

Then set the values supplied by Modal:

```dotenv
MODAL_API_KEY=your_modal_proxy_token
MODAL_BASE_URL=https://your-modal-api-base/v1
```

`MODAL_BASE_URL` is used exactly as written. It must be the API base URL, not a
specific `/models` or `/chat/completions` route. The provider selects its
available model automatically; there is no model-name environment variable.

The worker automatically loads `.env` from the plugin checkout without
overriding variables already exported by the shell. These optional settings
are only applied when present:

```dotenv
LLM_MAX_OUTPUT_TOKENS=4096
LLM_MAX_RETRIES=2
LLM_TIMEOUT_SECONDS=60
```

Without those variables, Vim Coach adds no project-level output-token, retry,
or timeout limit. If Modal is unavailable or unconfigured, batch analysis
falls back to locally generated candidates and reports the provider warning.

Setting `cloud_enabled = true` explicitly permits provider analysis. Keep it
`false` when source text must never leave the machine; capture and progress
tracking still run, but automatic analysis is disabled.

## Daily use

Edit normally. When Vim Coach recognizes a supported completed sequence, it
queues and analyzes it automatically. You do not need to run a command after
every edit.

Useful starting points:

```vim
:VimCoachHelp
:VimCoachStatus
:VimCoachGoals
:VimCoachStats
```

`VimCoachHelp` opens the complete in-editor command guide. Press `q` to close
the help, goals, or statistics buffer.

Each verified new concept becomes a goal. `:VimCoachGoals` supports:

- `j`/`k`: move through goals
- `Enter`: show goal details
- `x`: pause or resume a goal
- `r`: refresh
- `q`: close

The configured `goal_target` controls how many successful uses complete a
goal. A sequence can reinforce more than one concept—for example, `3w` can
advance both count and word-motion goals.

## Commands

| Command | Purpose |
| --- | --- |
| `:VimCoachHelp` | Open the command guide. |
| `:VimCoachStatus` | Show capture, queue, worker, and recorder status. |
| `:VimCoachPause` | Pause recording and automatic analysis. |
| `:VimCoachResume` | Resume recording and automatic analysis. |
| `:VimCoachSync` | Retry or manually send queued episodes. |
| `:VimCoachAnalyze` | Alias for `:VimCoachSync`. |
| `:VimCoachLesson` | Show the number of verified lessons ready. |
| `:VimCoachGoals` | Open learning goals and progress. |
| `:VimCoachStats` | Open learned-feature statistics. |
| `:VimCoachPractice` | Practice the latest captured edit in a scratch buffer. |
| `:VimCoachPracticeCheck` | Check the current practice result. |
| `:VimCoachPracticeReset` | Restore the practice buffer to its starting state. |
| `:VimCoachDismiss` | Dismiss the current legacy inline lesson. |
| `:VimCoachKnow` | Suppress the current legacy inline concept. |
| `:VimCoachResetData` | Clear queued in-memory episode data. |
| `:VimCoachResetProfile` | Confirm and erase persisted lessons, goals, and progress. |
| `:VimCoachResetProfile!` | Erase the profile without confirmation. |

Practice uses a scratch buffer and never modifies the source buffer.

## Configuration

These are the main `setup()` options and their defaults:

```lua
require("vim_coach").setup({
  enabled = true,
  cloud_enabled = false,
  idle_ms = 250,
  cooldown_ms = 60000,
  max_lines = 100,
  max_buffer_bytes = 8192,
  max_episode_keys = 128,
  max_episode_ms = 10000,
  max_candidates = 3,
  max_pending_episodes = 20,
  min_navigation_keys = 4,
  replay_timeout_ms = 1000,
  goal_target = 50,
})
```

`debug_prompt = true` writes captured request diagnostics and should only be
used deliberately because those logs can contain source text. `worker_command`,
`worker_cwd`, `history_file`, and `goals_file` are available for development
or custom storage setups.

## How verification works

For every candidate, Vim Coach launches a disposable headless Neovim process
and replays the original and proposed sequences. A coaching candidate is
accepted only when text, cursor, final mode, and final-newline state match.
Register differences are recorded but do not reject otherwise useful idioms
such as replacing repeated `x` commands with `D`.

Model output is treated as untrusted data. Candidate tokens must pass a strict
local schema and grammar. The replay process does not execute model-provided
Lua, Ex commands, shell commands, or arbitrary code.

## Local data and privacy

Vim Coach stores state under `~/.local/state/vim-coach/` by default:

- `lessons.json`: verified lesson metadata
- `goals.json`: goal status and aggregate usage counts

Set `VIM_COACH_HISTORY_FILE` or `VIM_COACH_GOALS_FILE` to override these paths.
Persisted records contain feature identifiers, bindings, counts, status, and
timestamps—not raw before/after source snapshots.

When provider analysis is enabled, the request contains the bounded episode's
before/after text, cursor state, original token sequence, allowed grammar, and
lesson context. Paths, registers, and unrelated buffers are not uploaded.

## Demo and development

An isolated profile is available for development:

```sh
nvim -u demo/minimal.lua
```

It keeps provider analysis disabled unless explicitly enabled:

```sh
VIM_COACH_CLOUD=1 nvim -u demo/minimal.lua
```

The guided playground is `vim-coach-playground.txt`.

Run the complete offline suite with:

```sh
python3 scripts/check.py
```

Run the deterministic 39-scenario catalog evaluation without a provider call:

```sh
python3 scripts/evaluate_coach.py --local-only
```

Run the live evaluation or provider diagnostic only when you intend to make
real endpoint requests:

```sh
python3 scripts/evaluate_coach.py
python3 scripts/provider_diagnostic.py --env-file .env --mode basic
```

The test suite itself makes no live provider requests.

## Current limitations

Vim Coach targets ordinary single-buffer editing with a curated command
grammar. It supports printable ASCII edits and bounded characterwise and
linewise Visual operations. It does not currently cover blockwise Visual mode,
arbitrary mappings or macros, pattern search, paste/register execution,
cross-file edits, Unicode literal changes, or VSCodeVim. Replay is a
deterministic correctness check, not a general operating-system sandbox.
