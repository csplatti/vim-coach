# Vim Coach

Vim Coach is a native Neovim prototype that will capture supported editing
episodes, suggest shorter Vim sequences, verify them by replay, and teach them
through a scratch-buffer drill.

The intended product direction is now a **batch review coach**: Neovim stays
quiet while you work, episodes are analyzed in batches, and verified lessons
appear in a separate review app rather than inline in the editor.

The recorder captures both edits and inefficient motion-only episodes. By
default, navigation must contain at least four supported keys and move the
cursor before it is queued, avoiding coaching for every ordinary movement.
Each manual sync analyzes every episode currently waiting in the queue.
Navigation analysis prefers unseen semantic motions over another example of
an already introduced count.

The current curated feature catalog contains 54 replay-supported help topics.
It includes counts; basic, word, line, file, pair, sentence, and paragraph
motions; character-find motions; word, quote, parenthesis, and brace text
objects; bounded delete/change operators; and single-character replacement.
The installed Neovim runtime has thousands of help tags, so this remains a
safe subset rather than a claim of full Vim coverage.

Recommendation discovery is hybrid. A local catalog generator creates bounded
programs from those features, the model may add contextual candidates, and
replay validates both sources identically. Modal failure no longer fails the
batch: local catalog candidates are still verified and persisted, with the
provider error returned as a warning. Lesson history is used as a small skill
profile so concepts already introduced, dismissed, or marked known are not
emitted as duplicate lessons.

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
registers. A batch replays the original sequence once per episode and reuses
that baseline for every candidate.

The standalone verifier defaults to strict register equality. Coaching uses an
explicit `editing-outcome` policy: text, cursor, final mode, and final-newline
state must match, while register differences are measured and disclosed rather
than rejecting idiomatic replacements such as `D` for repeated `x`. Lessons
must not describe these as full Vim-state equivalence.

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

## Modal proposal worker

Step 4 adds an opt-in local worker using Modal's OpenAI-compatible endpoint.
Configure credentials locally, outside Git:

```sh
export MODAL_API_KEY='...'
export MODAL_BASE_URL='https://inference.us-west.modal.direct/v1'
```

Copy `.env.example` to `.env` and replace the placeholder token and endpoint
URL from Modal's request example. `MODAL_BASE_URL` is used exactly as provided;
it should be the API base URL, not a specific `/models` or `/chat/completions`
request URL. Modal Shared Endpoints use a proxy token; the worker discovers the
available endpoint/model automatically.
`LLM_MAX_OUTPUT_TOKENS`, `LLM_MAX_RETRIES`, and `LLM_TIMEOUT_SECONDS` are all
optional. When absent, the worker does not impose those project-level limits
and leaves the provider client defaults in effect.

The worker refuses requests unless the input contains `cloudEnabled: true`.
It sends only minimized before/after text, cursor state, allowed grammar, and
the original token sequence; registers, paths, and unrelated editor state stay
local. Responses are validated and compiled locally before replay verification.

No live provider request is made by the test suite. To test the configured
endpoint after explicit approval, use the client from a controlled Python
session:

```python
from worker.provider import LLMClient, LLMConfig

client = LLMClient(LLMConfig.from_env(cloud_enabled=True))
print(client._model())  # auto
```

Then the JSON worker accepts an episode on stdin:

```sh
printf '%s' '{"schemaVersion":1,"cloudEnabled":true,"episode":{}}' \
  | python3 worker/main.py
```

The empty episode above is expected to fail locally; it is only a transport
smoke test and does not upload anything without valid credentials.

## Current batch-review prototype

Captured edits now enter a bounded in-memory queue. They do not trigger a
provider request or an inline card. Use `:VimCoachStatus` to see the pending
count, then `:VimCoachSync` to send up to five queued episodes in one worker
request. The worker validates the batch response, replay-verifies each
candidate, and keeps only verified lesson records in memory.

The batch worker also writes verified lesson metadata to
`~/.local/state/vim-coach/lessons.json` (or `VIM_COACH_HISTORY_FILE` when set).
Each review card introduces one reusable Vim feature with a feature title, a
concise excerpt from the installed Neovim runtime documentation, an example
binding, and the corresponding `:help` tag. AI prose is discarded before the
lesson is persisted, so lessons do not critique or narrate the user's edit.
The installed help catalog is also included in model context. For navigation,
the worker supplements model proposals with bounded candidates from the whole
supported feature catalog, including semantic motions, counts, delete forms,
motion-plus-delete sequences, and anchored edits. It accepts them only when
local replay proves the configured editing outcome. The model remains useful
for contextual proposals, but ordinary catalog coverage does not depend on it.
Raw before/after buffer snapshots are not persisted by default.

Use `:VimCoachLesson` to see how many lessons are ready. Neovim does not yet
launch or push to the review app automatically, so the old inline card remains
only as a legacy demo fixture (`demo/suggestion.lua`) and is not used by
automatic capture.

The first review-app shell is in `review_app/`. From that directory, run
`npm install` once and then `npm start`. It reads the same history file and
supports review, dismiss, I Know, reset, and an indeterminate loading bar while
the worker evaluates a batch. Practice is intentionally marked as the next
step because raw practice snapshots are not persisted.

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

Run the live coverage harness to generate, batch, and replay-verify navigation
and editing scenarios without typing them manually:

```sh
python3 scripts/evaluate_coach.py
```

This makes one provider batch request and reports proposed, verified, rejected,
and expected bindings for each scenario.

To measure deterministic catalog coverage without a provider request:

```sh
python3 scripts/evaluate_coach.py --local-only
```

The checked-in 39-scenario corpus currently verifies all 39 expected targets
under the coaching outcome policy. This is curated grammar coverage, not a
claim about all of Vim.

To diagnose the Modal/provider endpoint without printing the API key, run:

```sh
python3 scripts/provider_diagnostic.py --env-file .env --mode basic
```

To compare plain chat and JSON response modes, run this explicitly. It makes
three inference requests:

```sh
python3 scripts/provider_diagnostic.py --env-file .env --mode all
```

The output includes the provider response body, request IDs, latency, and a
likely diagnosis. Do not paste the API key or the full request headers into a
bug report.

The worker now sends each provider candidate through the replay verifier and
returns only verified, strictly shorter candidates. Provider failures,
timeouts, malformed candidates, and replay mismatches fail closed. A live
Modal request requires explicit opt-in, an API token, and an approved
spending limit; the test suite never makes live requests.

The provider worker uses the pinned OpenAI-compatible client in
`requirements.txt`. It requests plain
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

When `cloud_enabled = true`, the plugin starts the local worker only after a
manual `:VimCoachSync` (or the backwards-compatible `:VimCoachAnalyze`).
Completed captures remain local until that batch trigger. The default
configuration keeps cloud analysis disabled.

The minimal demo reads that opt-in from `VIM_COACH_CLOUD`:

```sh
VIM_COACH_CLOUD=1 nvim -u demo/minimal.lua -i NONE -n
```

The development demo enables `debug_prompt = true`. The Electron process tails
the local debug stream and prints the formatted LLM request, response, and replay
result in the terminal running `npm start`. Restart the Electron app after code
changes to enable the watcher. Debug requests include captured buffer text, so
keep the option disabled for private files.

The review inbox updates through a filesystem watcher on `lessons.json`; lesson
cards are pushed to the renderer over Electron IPC rather than polled. Worker
status remains polled for the short-lived loading indicator.

## Current limits

The finished prototype is intentionally bounded: one native Neovim profile,
ordinary file buffers, printable ASCII literal edits, and a curated command
grammar. It captures Normal and Insert mode plus bounded characterwise and
linewise Visual edits. Blockwise Visual mode, arbitrary mappings, macros,
pattern search, paste/register execution, cross-file edits, Unicode literal
changes, and VSCodeVim integration remain future work. The replay child is a
deterministic process, not a general OS security sandbox.

## Next architecture: batch review app

The next implementation should follow this loop:

```text
Neovim capture → local queue → batched LLM request → replay verification
→ persisted lesson inbox → separate review/practice app
```

Neovim must not call the provider or open a suggestion card after each edit.
It should only record bounded episodes, show a quiet pending-count/status
indicator, and expose a manual `:VimCoachSync` command. An explicit sync sends
every episode currently waiting in the bounded local queue.

The local worker accepts an array of episodes, asks the model for suggestions,
replay-verifies every candidate, and persists only verified lesson metadata.
Source snapshots should remain ephemeral by default; persisted history should contain tokens, concepts,
explanations, counts, timestamps, and verification scope unless the user
explicitly opts into keeping practice examples.

The separate app can start as an Electron review inbox backed by a local JSON
or SQLite state directory. It should provide Review, Practice, Dismiss, I
Know, and Reset controls. No public backend, account system, or vector database
is required for the first version. Retrieval can begin with concept IDs,
token-pattern matching, and recent practice history; add embeddings only if
that simple retrieval is demonstrably insufficient.

Implementation order:

1. Replace per-episode worker calls with a bounded local queue.
2. Add a batch request/response contract keyed by episode ID.
3. Add local lesson history and retrieval without raw source by default.
4. Preserve replay verification as the acceptance gate for every suggestion.
5. Build the separate review app and local IPC/state protocol.
6. Move Practice, Dismiss, I Know, and cooldown state into the review app.
7. Remove or disable the inline suggestion card and measure review/practice
   completion.

Available commands:

```text
:VimCoachPause
:VimCoachResume
:VimCoachStatus
:VimCoachSync
:VimCoachAnalyze
:VimCoachLesson
:VimCoachDismiss
:VimCoachKnow
:VimCoachPractice
:VimCoachPracticeCheck
:VimCoachPracticeReset
:VimCoachResetData
```
