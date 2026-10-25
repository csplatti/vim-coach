# Vim Coach

Vim Coach is a native Neovim prototype that will capture supported editing
episodes, suggest shorter Vim sequences, verify them by replay, and teach them
through a scratch-buffer drill.

## Development baseline

The current development machine has:

```text
NVIM v0.9.4
LuaJIT 2.1.1700008891
```

The demo profile is tested against Neovim 0.9.4. Verify the executable with:

```sh
nvim --version
```

## Run the minimal profile

From the repository root:

```sh
nvim -u demo/minimal.lua
```

This loads the plugin directly from the checkout with local recording enabled
and cloud analysis disabled. The recorder currently supports bounded ASCII
Normal-mode motion and deletion episodes. It waits for the configured idle
boundary, discards navigation-only edits, and keeps snapshots in memory.

To see capture status without source text:

```vim
:VimCoachStatus
```

## Replay verifier

Step 3 adds a standalone deterministic verifier. It launches a fresh headless
Neovim child for the original and candidate token arrays, then compares the
resulting buffer, final-newline state, cursor, Normal mode, and tracked
registers. The candidate is accepted only when both replays match the target
and the candidate uses fewer logical tokens.

The verifier accepts a JSON payload containing `before`, `after`,
`originalTokens`, and `candidateTokens`:

```sh
python3 replay/verify.py payload.json
```

Run the checked-in fixture with:

```sh
python3 replay/verify.py tests/fixtures/replay-basic.json
```

It should report `accepted: true`, with the candidate saving one logical key.

The child receives structured JSON and a validated token array only. It does
not execute model-provided Lua, Ex commands, shell commands, or arbitrary
source text.

## Bitdeer proposal worker

Step 4 adds an opt-in local worker. Bitdeer uses the documented OpenAI-
compatible base URL and bearer authentication. Configure credentials locally,
outside Git:

```sh
export BITDEER_API_KEY='...'
```

`BITDEER_MODEL` is optional. If omitted, the worker calls `/models` and
selects a preferred text model automatically, starting with
`deepseek-ai/DeepSeek-V4-Flash`. Set `BITDEER_MODEL` only when you want to
override that choice.

The worker refuses requests unless the input contains `cloudEnabled: true`.
It sends only minimized before/after text, cursor state, allowed grammar, and
the original token sequence; registers, paths, and unrelated editor state stay
local. Responses are validated and compiled locally before replay verification.

No live provider request is made by the test suite. To discover models after
explicit approval, use the client from a controlled Python session:

```python
from worker.bitdeer import BitdeerClient, BitdeerConfig

client = BitdeerClient(BitdeerConfig.from_env(cloud_enabled=True))
print(client.list_models())
```

Then the JSON worker accepts an episode on stdin:

```sh
printf '%s' '{"schemaVersion":1,"cloudEnabled":true,"episode":{}}' \
  | python3 worker/main.py
```

The empty episode above is expected to fail locally; it is only a transport
smoke test and does not upload anything without valid credentials.

## Suggestion card

Step 5 adds a single floating suggestion card for proposals that have already
passed local replay verification. The card shows the original and candidate
logical-key counts, the explanation, and only the comparison scope actually
reported by verification. Use `:VimCoachLesson` to reopen it,
`:VimCoachDismiss` to start the cooldown, or `:VimCoachKnow` to suppress the
concept in the current session. The Bitdeer worker is not automatically
called yet; a future integration will pass its verified result to
`require("vim_coach").show_suggestion(...)`.

## Practice drill

Step 6 opens the last captured episode in a scratch buffer with
`:VimCoachPractice`. The source buffer is never edited. Use
`:VimCoachPracticeCheck` to compare the scratch buffer with the captured
target, or `:VimCoachPracticeReset` to restore its starting state. Practice
buffers are excluded from automatic recording.

## Offline demo and checks

The suggestion-card demo uses a labeled local fixture and makes no provider
request:

```sh
nvim -u demo/suggestion.lua
```

Run the complete offline check before recording a demo:

```sh
python3 scripts/check.py
```

To diagnose Bitdeer without printing the API key, run the model-list check:

```sh
python3 scripts/bitdeer_diagnostic.py --env-file .env --mode models
```

To compare the plain chat request, legacy JSON mode, and strict JSON Schema
mode, run this explicitly. It makes three inference requests:

```sh
python3 scripts/bitdeer_diagnostic.py --env-file .env --mode all
```

The output includes the provider response body, request IDs, latency, and a
likely diagnosis. Do not paste the API key or the full request headers into a
bug report.

The worker now sends each provider candidate through the replay verifier and
returns only verified, strictly shorter candidates. Provider failures,
timeouts, malformed candidates, and replay mismatches fail closed. A live
Bitdeer smoke request still requires your explicit approval, API key, model,
and spending limit; it has not been run from this checkout.

The provider worker uses the pinned OpenAI-compatible client in
`requirements.txt`, matching Bitdeer’s official example. It requests plain
chat-completion mode for broad deployment compatibility, then applies the
complete local candidate schema and replay verifier. On Apple Silicon systems
running an x86_64 Neovim, the demo prefers `.venv-x86` automatically.

Install it with:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

If Neovim is x86_64 under Rosetta, install the matching worker environment:

```sh
arch -x86_64 python3 -m venv .venv-x86
arch -x86_64 .venv-x86/bin/python -m pip install -r requirements.txt
```

For the current proposal prompt, the tested automatic choice is:

```sh
BITDEER_MODEL=deepseek-ai/DeepSeek-V4-Flash
```

`DeepSeek-V4.1-Flash` is reachable, but it spends the bounded completion
budget on hidden reasoning for this task and may return no text content.

When `cloud_enabled = true`, the plugin starts the local worker after a
completed capture and ignores stale results from superseded episodes. Use
`:VimCoachAnalyze` to retry the latest captured episode manually. The default
configuration keeps this path disabled.

The minimal demo reads that opt-in from `VIM_COACH_CLOUD`:

```sh
VIM_COACH_CLOUD=1 nvim -u demo/minimal.lua -i NONE -n
```

## Current limits

The finished prototype is intentionally narrow: one native Neovim profile,
ordinary file buffers, bounded ASCII Normal-mode motion/deletion commands, and
in-memory episode state. Visual mode, insert/change proposals, mappings,
macros, search, paste, cross-file edits, and VSCodeVim integration remain
future work. The replay child is a deterministic process, not a general OS
security sandbox.

Available commands:

```text
:VimCoachPause
:VimCoachResume
:VimCoachStatus
:VimCoachAnalyze
:VimCoachLesson
:VimCoachDismiss
:VimCoachKnow
:VimCoachPractice
:VimCoachPracticeCheck
:VimCoachPracticeReset
:VimCoachResetData
```
