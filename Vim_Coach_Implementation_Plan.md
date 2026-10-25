# Vim Coach Implementation Plan

**For Corbin · Solo Cal Hacks build · October 24–25, 2026**

## 1 The project and the decision

Build a **native Neovim plugin that automatically records editing episodes**, suggests a shorter sequence, verifies it by replay, and teaches the technique through a drill made from your own edit. The model proposes and explains; deterministic code decides whether a proposal works.

**Automatic recording is core, not a stretch goal.** You should not have to click Start and Finish around each edit. Use Neovim’s input callbacks plus buffer, cursor, and mode snapshots to identify short completed episodes. Make one editor setup reliable before adding more.

You currently use **VSCodeVim**. This MVP would run in **native Neovim**, outside VS Code; it is not a drop-in extension for VSCodeVim. A VS Code companion cannot obtain a complete Vim key stream through ordinary document-change events. VSCode-Neovim is also a separate integration, with native VS Code editing paths that require extra instrumentation. Do not spend tonight building both adapters. [VSCodeVim input routing](https://github.com/VSCodeVim/Vim/blob/master/extensionBase.ts)

The product loop is:

**Edit normally → recognize a completed edit → propose shorter alternatives → replay and compare → offer one lesson → practice on a scratch copy.**

### Revised product direction: batch review, not inline coaching

The product direction has changed after testing the live loop. Do not interrupt
editing with an immediate model request or inline suggestion card. The desired
loop is:

**Edit normally → queue bounded episodes locally → send a batch to the model → replay-verify candidates → review lessons in a separate app → practice later.**

Neovim remains a quiet recorder and status surface. It may show a pending
lesson count, but it should not open a suggestion card after each edit. The
model remains responsible for proposing and explaining techniques; local
parsing and replay remain the correctness boundary.

The separate review app should begin as a local Electron inbox backed by a
JSON or SQLite state directory. It should support Review, Practice, Dismiss, I
Know, and Reset. No public backend, account system, or vector database is
needed for the first batch-review version.

The model request should contain multiple episode IDs and minimized examples.
The response must identify each episode, contain bounded candidate proposals,
and never claim verification. The worker verifies every candidate separately,
discards failures, and writes only verified lesson metadata to the local
inbox. Persist raw source snapshots only with explicit user opt-in; otherwise
retain them in memory until replay and practice finish.

This replaces the earlier inline-card requirement below. The existing card is
useful as a prototype fixture but is not the target user experience.

### Improved recommendation architecture

Do not make model recall the coverage boundary. Generate a bounded candidate
set locally from the supported Vim feature catalog, merge it with optional
model proposals, and send both through the same replay verifier. Local
generation covers semantic motions, counts, deletion commands, common
motion-plus-action combinations, and anchored edits; it never marks its own
candidate correct.

Replay the captured original once per episode, then compare each candidate
against that baseline. Coaching uses an explicit editing-outcome policy: text,
cursor, final newline, and mode must match. Register differences remain in the
verification record but do not reject an otherwise useful lesson. This is
weaker than full-state equivalence and must be labeled as such.

Use persisted lesson metadata as a small curriculum profile. Suppress repeated,
dismissed, and known concepts; rank the remaining features by keys saved,
feature usefulness, and simplicity. A provider failure should produce a warning and fall back to local
catalog candidates instead of discarding the whole batch. The model remains a
source of contextual proposals, not the parser, verifier, documentation source,
or sole source of feature discovery.

**Done means:** automatic capture works on three real supported edits; a shorter candidate is verified; an incorrect or unsafe proposal is rejected; one drill works without touching the source file; a real Modal response drives the experience; and another person can reproduce the demo from the README. Do not promise universal Vim equivalence, physical keystroke measurement, improved typing speed, novelty, or a prize.

## 2 What the user sees

1. Enable the plugin in a clean Neovim demo profile and explicitly opt into model analysis for a non-sensitive project. A small status indicator shows **Coach on**.
2. Edit normally. The plugin records supported logical inputs into bounded memory; it does not make a model request on every key.
3. After a short edit ends in Normal mode and the user pauses, the plugin freezes the before/after episode. Navigation without an edit is discarded for P0.
4. A local eligibility check and original-sequence replay establish that the captured inputs explain the captured change. Eligible episodes enter the local batch queue.
5. On a batch trigger, send minimized episodes to the worker. Validate the response, replay candidates in disposable headless Neovim processes, and reject mismatches or unsafe syntax.
6. Persist only verified lesson metadata in the local inbox. Each lesson introduces one reusable Vim feature using a concise excerpt and help tag from the installed Neovim runtime documentation; discard AI teaching prose rather than explaining a user mistake. Show a quiet pending count in Neovim; do not open an inline suggestion card.
7. The separate review app shows one lesson at a time. Practice opens a scratch buffer containing the original example; **Check** compares the result with the target, and **Reset** restores the start.

Example wording, with counts filled from actual results:

> Try this shorter sequence. Same captured buffer, cursor, and Normal mode in replay. Register effects differ. 9 → 4 logical Vim keys. Practice this edit?

Only claim the states actually compared. A replay proves this concrete example under a defined profile, not equivalent behavior in every file or editor configuration.

## 3 Scope that fits one night

### P0 required

- One native Neovim version and a clean demo configuration.
- Automatic recording and episode boundaries; pause/status commands only, not manual recording as the normal workflow.
- One ordinary file buffer, one cursor, Normal-mode start and end, small ASCII examples.
- A small vocabulary of navigation and deletion commands, with insert/change added only after the first loop works.
- Real Modal candidate generation; local safe parsing and deterministic replay.
- One bounded batch queue, verified lesson records, and one scratch-buffer drill;
  the separate review app replaces the inline card.
- Tests, honest unsupported-state behavior, privacy controls, and reproducible demo materials.

### P1 only after P0 works

- Safe literal insertion and word-replacement proposals.
- A small local concept history and cooldown tuning.
- More command families and Unicode after position/key normalization tests pass.
- A polished floating window instead of a basic scratch panel.

### P2 after the hackathon

VSCodeVim instrumentation, VSCode-Neovim integration, arbitrary mappings/macros, visual selections, cross-file edits, LSP-aware behavior, generated drill variants, and longitudinal learning evaluation.

**Do not build:** OS-wide Vim controls, a Vim replacement, accounts, a public backend, fine-tuning, embeddings, a vector database, mobile support, or autonomous code editing. This is an inference-and-validation systems project, not a model-training project.

## 4 First hour automatic capture gate

Pin one tested Neovim release; **0.11.4 is a concrete documentation baseline, not a claim that it is the latest release**. Use the same installed executable for interactive editing and replay. Record its version in the README.

Neovim exposes `vim.on_key(function(key, typed) ... end, namespace)`. In the pinned documentation, `key` is the processed key after mappings, `typed` reflects typed input before mappings, and the callback runs before the key is processed. Empty or multi-key `typed` values require care. One callback is not necessarily one physical keypress. A callback error can remove the listener. [Pinned Neovim callback documentation](https://github.com/neovim/neovim/blob/v0.11.4/runtime/doc/lua.txt#L1460-L1487)

Build this spike before the model or UI:

1. Load a tiny Lua plugin in native Neovim and register exactly one namespaced callback.
2. Capture printable ASCII and explicitly normalized supported controls into a bounded ring. Store typed and resolved input separately; never add both to the key count.
3. Return `nil`, not an empty string. Protect bookkeeping with `pcall`; on failure, disable recording visibly and expose a status/health command. Do not let a broken coach change editor input.
4. Before the first eligible Normal-mode key, capture the complete bounded buffer and starting state. The first snapshot must happen before mutation; scheduling it later would lose the start.
5. Make a short movement-plus-delete edit. After a quiet interval, capture the settled target. Print a local debug report with text omitted by default.
6. Replay the original supported inputs from the captured start and confirm the target. Repeat with Escape, counts, and rejected paste/remap cases.

**Gate after 45–60 minutes:** reliable automatic capture, complete boundaries, known input provenance, and no editing interference on the selected profile. If this fails, cut supported commands and configuration complexity—not the automatic-recording requirement. A manually prepared recording can help debug but is not a substitute for the promised product.

## 5 Stack and repository

Use **Lua for the Neovim plugin and a small Python worker for HTTP and subprocess orchestration**. This uses your Python experience without creating a web service. The Lua you need is bounded: callbacks, autocommands, tables, scheduled work, buffers, and process communication.

- Neovim Lua API for recording, state snapshots, commands, and UI.
- `vim.system` or an equivalent verified asynchronous process API to launch the worker with JSON on stdin and a bounded JSON result on stdout.
- Python standard-library HTTP support or a small pinned HTTP client; JSON/schema validation with a pinned library if it saves time.
- A fixed Lua replay harness in disposable headless Neovim children. Communicate via structured data, never generated source code.
- Python tests for parsing/orchestration and headless Neovim fixture tests for editor behavior.
- Direct HTTPS from the local worker to Modal. No public backend or account system.

The exact replay transport—fixed Lua script reading JSON stdin or a tested RPC client—is a Phase 2 implementation choice. Prove one before building around it. With RPC, enqueueing input is asynchronous and does not mean the edit has finished. Do not invent an SDK method or treat an immediate response as settled state. [Neovim API reference](https://neovim.io/doc/user/api)

Prerequisites: Git, Python, native Neovim, an API key and approved spending limit, a small non-sensitive demo project, and a screen recorder. Verify `nvim --version`, a Lua callback, a headless child, and one approved provider request. Lock dependencies and record actual versions.

```text
vim-coach/
  plugin/vim_coach.lua          # commands and initialization
  lua/vim_coach/
    init.lua                   # setup and configuration
    recorder.lua               # key hook and bounded memory
    episodes.lua               # state machine and invalidation
    snapshot.lua               # buffer/cursor/mode/registers/options
    worker.lua                 # asynchronous process lifecycle
    ui.lua                     # legacy suggestion fixture only
    practice.lua               # scratch buffer, reset, check
    privacy.lua                # scope, preview, exclusions
  worker/
    main.py                    # JSON input/output, orchestration
    contracts.py               # runtime schema validation
    grammar.py                 # stateful parser and trusted compiler
    rules.py                   # static comparison baseline
    provider.py                # Modal/OpenAI-compatible request lifecycle
    replay.py                  # child deadlines and result comparison
  replay/runner.lua            # trusted fixed harness only
  tests/fixtures/              # before/after/input/expected verdict
  scripts/benchmark.py
  demo/minimal.lua              # known configuration
  README.md
```

### Starter configuration and commands

Implement this public interface in your plugin; these are proposed names, not an existing package API. Add the repository to Neovim’s runtime path in `demo/minimal.lua`, then call:

```lua
require("vim_coach").setup({
  enabled = true,                 -- automatic local recording
  cloud_enabled = false,          -- enable only after explicit opt-in
  idle_ms = 1000,
  cooldown_ms = 60000,
  max_lines = 100,
  max_buffer_bytes = 8192,
  max_episode_keys = 128,
  max_episode_ms = 10000,
  max_candidates = 3,
  provider_timeout_ms = 10000,
  replay_timeout_ms = 1000,
})
```

Expose `:VimCoachPause`, `:VimCoachResume`, `:VimCoachStatus`, `:VimCoachSync`, `:VimCoachLesson`, `:VimCoachPractice`, and `:VimCoachResetData`. Pause cancels capture and pending uploads; Resume restores recording only within the approved scope. Status reports capture health, cloud opt-in, pending batch count, verified lesson count, and the latest skip reason without source text. Lesson reports the review inbox count until the separate app is connected; Practice opens a scratch copy. ResetData clears local history and pending snapshots, with a confirmation prompt. The practice panel also needs Check and Reset controls.

## 6 State and episode boundaries

This is a **data design sketch**, not a complete implementation:

```text
Snapshot
  lines, finalNewline, bufferId, changedtick
  cursor {row1Based, byteColumn0Based}, mode
  relevantOptions, trackedRegisters, profileId

Episode
  id, generation, before, after
  typedTokens, resolvedTokens, originalLogicalKeyCount
  provenanceFlags, startedAt, endedAt

Proposal
  tokens: bounded array of typed SafeToken objects
  concept: bounded string
  explanation: bounded string, never executable

Verification
  originalReplayMatches, candidateReplayMatches
  textEqual, cursorEqual, modeEqual, registersEqual
  originalLogicalKeys, candidateLogicalKeys, savedLogicalKeys
  profileId, rejectionReason, replayLatencyMs
```

Keep raw snapshots and registers local. Provider payloads are separate, minimized objects. Never send buffer paths or register contents merely because they exist in the local contract.

A concrete model-response contract can start with:

```json
{
  "schemaVersion": 1,
  "candidates": [
    {
      "tokens": [
        {"kind": "count", "value": 4},
        {"kind": "move", "key": "h"},
        {"kind": "delete", "command": "x"}
      ],
      "concept": "counted-movement",
      "explanation": "Use a count instead of repeating the movement."
    }
  ]
}
```

This is a **proposal-format example, not a verified fixture**. Define `SafeToken` as a discriminated union: count with bounded integer `value`; move with an enumerated `key`; delete with an enumerated `command`. Require all fields, set `additionalProperties: false` on every object, limit candidates to three, bound token arrays and strings, and validate count placement with the stateful grammar after schema validation. The provider cannot supply accepted savings or verification status; the local compiler and replay engine compute them. Reject unknown schema versions and malformed responses rather than coercing them.

Use `idle → recording → settling → queued → analyzing → ready`, with cancellation/unsupported exits. Permit recording only in approved, modifiable ordinary file buffers. Exclude terminal, prompt, command-line, help, plugin UI, practice, and secret/excluded buffers. Do not log command-line input.

**Start:** the first supported Normal-mode key after idle captures before-state. Include its navigation prefix; otherwise you cannot recognize inefficient movement before the edit.

**Continue:** append supported tokens and mark changes. `TextChanged`, `TextChangedI`, and `ModeChanged` mark the episode dirty and schedule work; event counts are not key counts. Keep the input hook cheap: no network, disk, model calls, or expensive whole-buffer copy on every key.

**Seal:** after roughly 800–1200 ms idle, schedule a generation-guarded finalizer. Require the same buffer/window, exact Normal mode, a complete original-command grammar, and a real text change. Capture after-state only when input has settled. `InsertLeave` alone is not a sufficient boundary; some exits do not trigger it. [Pinned event documentation](https://github.com/neovim/neovim/blob/v0.11.4/runtime/doc/autocmd.txt)

**Discard:** command-line entry, buffer/window switch, focus loss, macro execution/recording, uncertain remapping, paste/IME, unsupported special input, oversized episode, or unaccounted external change. Detect obvious causes; the original replay gate catches discrepancies you missed. Never silently “repair” missing keys by asking the model to guess them.

Every async job carries episode ID, generation, buffer identity, and target `changedtick`. Cancel superseded work; ignore late results. If the source has changed, keep a result only as an explicitly historical practice example, not a current instruction. Limit the queue to one active and one latest pending episode.

Suggested limits: complete buffer at most 100 lines or 8 KiB, episode at most 10 seconds/128 logical inputs, three candidates, one active provider request, and one active replay. Fail closed when exceeding limits. Do not crop the replay buffer and then claim whole-buffer equivalence.

## 7 What verification means

### Capture a profile rather than promising universal equivalence

Use the same executable (`vim.v.progpath`) and deterministic options in both replay runs. P0 supports standard mappings and a controlled configuration. Reject custom mappings or settings affecting allowed commands unless you explicitly reproduce and test them. Snapshot relevant word/indent options; avoid folds, virtual editing, clipboard integration, and plugin-generated transformations in the demo profile.

Capture complete text, final-newline state, cursor, Normal-mode boundaries, and the register state relevant to your grammar. For delete/change operations, track unnamed, small-delete, and numbered registers with contents and register types. Keep those values local and initialize the replay from the same captured values. Reject commands that depend on other registers or hidden editor state.

Replay the **original and candidate separately**, each from a fresh identical before-state:

1. Original must reproduce the captured target; otherwise the episode is unsupported or capture is incomplete.
2. Candidate must reproduce the target buffer, cursor, final-newline state, and mode. Compare tracked registers too, but under the coaching policy report differences rather than rejecting the visible editing outcome.
3. Candidate’s compiler-computed logical-key count must be strictly lower before calling it shorter.

The verifier supports two explicit policies. Standalone verification defaults to
`full-state`, where register differences reject a candidate. The coach uses
`editing-outcome`, where register equality is recorded but only buffer,
final-newline, cursor, and mode determine acceptance. This permits useful
lessons such as replacing repeated `x` with `D` or `diw` while making the
weaker guarantee visible. Never call an editing-outcome result full-state
equivalence. Undo history, dot-repeat, marks, jump lists, viewport, and future
behavior remain outside both prototype claims.

### A bounded grammar is the safety boundary

Do not accept a raw Vim command string from the model. Accept a bounded typed token array and validate the complete sequence with a stateful parser. Initial vocabulary:

- `move`: `h`, `l`, `w`, `b`, `e`, `0`, `^`, `$`.
- `count`: integer 1–20, only where the next complete command permits it.
- `delete`: `x`, `D`, `dd`, `dw`, `diw`, `daw`.
- P1: an explicitly defined change-word action plus literal ASCII text and Escape.

This deliberately excludes vertical-motion preferred-column state initially. Add families only after fixtures pass. A trailing count or operator is incomplete, not a valid episode.

Reject Ex commands, shell escapes, expression registers, macros, register execution, dot-repeat, clipboard/register-dependent paste, search, arbitrary `g` commands, file/window operations, model-supplied Lua, and unknown control inputs. Apply the grammar to **both original and candidate** before replay. Source comments and model explanations are untrusted data, including instructions embedded in code.

For insert/change support, literal text must remain data. Use a trusted insertion/paste API after establishing Insert mode, or a rigorously tested literal path. Reject control bytes, Escape, NUL, and unsupported newlines; do not interpret `<...>` text as special-key notation. Generate displayed commands and counts from the same trusted compiler.

### Disposable replay processes

Launch with fixed argument arrays, never shell interpolation. A useful startup baseline is `--headless -u NONE -i NONE -n --noplugin`, plus `--embed` only if using RPC. Load only the fixed trusted harness. Disable modelines, local init, autocommands, swap/backup/shada, and user plugins. Use a temporary working directory and unnamed in-memory buffer.

Scrub the child environment, especially API keys. Supply buffer content and captured state as structured data, never interpolated Lua/Ex source. Feed only compiled safe input, wait for an explicit settled-state completion signal, then read and compare results. Ensure the transport does not deadlock while the harness waits for input.

Enforce a parent-side wall deadline and output cap; terminate the process group and clean up in `finally`. Start with 1 second per replay and 32 KiB output, then tune from measurements. Fresh children are easier than state-reset bugs tonight. A clean Neovim process is **not an OS security sandbox**: schema plus complete grammar validation is the primary boundary, with OS resource/filesystem/network limits where practical. The harness must never execute shell commands, access user files, or write edits to disk. [Neovim startup reference](https://neovim.io/doc/user/starting)

### Count honestly

Measure **logical Vim input tokens**, not hardware events: Escape is one token, digits count individually, and uppercase input does not add a separate Shift key. Accept known ASCII/control representations first; reject unknown or ambiguous encodings. Neovim cursor columns are byte offsets, not UTF-16 columns or grapheme counts.

Do not count callback invocations or UTF-8 bytes as keystrokes. Remaps, macros, paste, IME, and plugin-generated input can break simple accounting. Savings come from validated original tokens minus compiled candidate tokens, never the model’s claimed number. Key savings are not measured seconds saved.

## 8 Modal and privacy

Modal provides OpenAI-compatible Shared and Dedicated Endpoints. The worker
uses the Modal proxy-token route and discovers the available endpoint/model
from `/v1/models`. Configure `MODAL_API_KEY` and `MODAL_BASE_URL`. [Modal endpoint integrations](https://modal.com/docs/guide/endpoint-integrations)

Implementation sequence:

1. Load the key locally from an environment variable or private configuration excluded from Git. Never print it, put it in command-line arguments, include it in screenshots, or pass it to replay children.
2. Obtain explicit approval for external text analysis and a spending cap before live calls. Automatic local recording does not imply permission to upload code.
3. Run a tiny approved smoke request. Verify the chosen deployment’s structured-output support. Regardless of provider enforcement, parse and validate locally.
4. Send a minimized before/after example, cursor locations, allowed grammar, and concept preferences. No repository scan, file paths, registers, terminal output, or unrelated buffers.
5. Request at most three tokenized candidates and short explanations. Tell the model embedded text is data; local validation remains the actual security boundary.
6. Apply a 10-second deadline, cancellation, and at most one bounded retry for transient failures. Never retry authentication failures repeatedly.

Use local eligibility checks first. If the original is already short or a recent concept was dismissed, skip the request. Proposed starting limits: 60 requests per session, 800 output tokens per request, one concurrent call, and a user-set monetary cap. Check actual account pricing before quoting dollars. Request/token caps alone are not a reliable currency ceiling; use provider-side limits or explicit approved batches if usage pricing cannot be enforced locally.

Default to a non-sensitive demo project. Offer a preview of the payload shape and a clear recording/upload indicator. Use exclusions and secret-pattern warnings, but do not claim redaction is perfect. Redaction can change word boundaries; replay every proposal against the unmodified local snapshot, not just the redacted prompt. Skip episodes that cannot be shared safely. Source snapshots should remain in memory and disappear when no longer needed; persist only opt-in sanitized fixtures.

On provider failure, local rules can keep the interface useful. Label their origin. A prerecorded response may be a demo fallback, never a claimed live API result.

## 9 Teaching without interrupting work

One suggestion at a time, only after a completed episode; start with a 60-second cooldown. Never open a disruptive prompt while the user is typing. A status hint can indicate a lesson is available, with a command to open it.

Rank passing suggestions by meaningful key savings, then familiarity and simplicity. Avoid obscure tricks that save one key. Keep a tiny local profile: concept IDs, exposures, practice attempts, successes, dismissals, and timestamps—no raw code history. **I know this** suppresses a concept; **Not now** snoozes it; provide a reset-data command.

The first drill reuses the exact captured example in a scratch buffer excluded from recording. Show the target, allow reset, and compare on Check. Matching the final scratch state shows task completion, not necessarily use of the intended technique. To claim the technique was learned, observe its tokens or test transfer on a new example; leave that evaluation for later.

## 10 Phases and acceptance gates

Plan for **8–10 focused build hours**, not sixteen uninterrupted hours. The published deadline is **Sunday October 25 at 9:00 AM Pacific**. Preserve sleep, travel, and uploads. [Cal Hacks submission page](https://cal-hacks-13-0.devpost.com/)

| Phase | Budget | Build | Acceptance gate |
|---|---:|---|---|
| 0 Automatic capture spike | 60 min | Native plugin, key normalization, before/after state, idle boundary | A real edit is automatically captured without changing behavior |
| 1 Contracts and fixtures | 45 min | State machine, grammar, profile, three examples | Supported and unsupported cases are explicit |
| 2 Replay verifier | 90 min | Fresh child, original replay, candidate replay, comparison, timeout | Good candidate passes; wrong and malicious inputs fail |
| 3 Model loop | 60 min | Approved API smoke test, schema, worker, ranking | A real Modal response produces a verified shorter sequence |
| 4 Coaching and practice | 60 min | Minimal card, cooldown, scratch/reset/check | Entire loop works without applying to source |
| 5 Reliability | 45 min | Cancellation, stale state, edge tests, privacy, cleanup | No false pass in the fixture suite |
| 6 Demo and packaging | 60 min | README, clean-start test, screenshot, recording, metrics | Another person can reproduce the demo |
| 7 Reserve | 60–120 min | Fix only core failures and complete submission | Working narrow product submitted on time |

Suggested rhythm: build until about 12:30 AM, sleep until about 5:30 AM, then QA and submit. Allow travel to the venue by 8 AM if required for your participation. Recalculate from the actual start; start uploads early. Cut features before cutting all sleep.

**Cut order:** generated drill variants → personalization history → polished UI → insertion/change support → additional command families. Preserve automatic capture, safe replay, real sponsor integration, and one successful drill. If capture or replay is unreliable, shrink to a clean config and fewer commands; do not conceal the failure behind a canned “live” demo.

## 11 Tests and evidence

Fixtures contain start/target text, final-newline state, cursor/mode/registers/options, original tokens, candidate tokens, and expected verdict. Generate targets from real editor runs. The examples in this plan are test ideas, not already executed results.

- **Positive:** redundant horizontal/word navigation followed by the same delete operation; a line-end deletion; a counted movement improvement. Add word replacement only after safe literal handling works.
- **Mismatch:** wrong word, same text with wrong cursor, or wrong final mode. Test register differences as a rejection under `full-state` and a disclosed difference under `editing-outcome`.
- **Capture:** idle boundaries, typeahead, incomplete count/operator, Escape, callback exception, buffer/window/focus changes, macro/remap/paste/IME rejection, plugin edits.
- **Encoding:** tabs, empty buffer, trailing newline, final line, CRLF policy, non-ASCII rejected until byte/token handling is tested.
- **Hostile proposals:** Ex/shell commands, macros, expression registers, invalid token placement, oversized arrays, control bytes, malformed JSON, and prompt-injection comments.
- **Operational:** child timeout/crash, process cleanup, provider 401/429/5xx, network loss, exhausted budget, cancellation, and stale results after new edits.

Freeze a small **12–20 episode** set before prompt tuning. Compare static rules alone with rules plus model proposals under the same grammar and verifier. Report supported-episode coverage, original-replay pass rate, accepted/rejected candidates, logical keys saved on validated episodes, replay/provider latency, and drill completion. Show unsupported episodes separately. This is a curated prototype evaluation, not proof of general productivity improvement.

## 12 Demo and submission

Three-minute story:

- **0:00–0:25:** Explain the real problem: you use Vim but repeat inefficient edits and want to learn without leaving your work.
- **0:25–1:15:** Edit naturally in native Neovim. Show automatic episode capture, a real model proposal, and the verified shorter sequence.
- **1:15–1:50:** Show an incorrect proposal rejected, then complete the scratch drill.
- **1:50–2:25:** Explain the engineering: input capture, bounded grammar, original/candidate replay, state comparison, and async isolation.
- **2:25–3:00:** Show measured test results, limitations, and the path toward your VSCodeVim workflow.

Target **Best Solo Hack** through real candidate generation and explanation. Confirm the submission selections and sponsor-specific requirements; no architecture guarantees an award. [Cal Hacks prizes and requirements](https://cal-hacks-13-0.devpost.com/)

Acknowledge prior art. [`hjkl`](https://pkg.go.dev/github.com/waaldev/hjkl) already describes shorter last-edit suggestions with headless replay verification; [`tobira.nvim`](https://github.com/kamegoro/tobira.nvim) offers personalized command discovery. Do not claim those ideas are inventions. Your implementation focus is a reliable automatic coach, replay validation, and practice that fits your own use. Those are not established unique differentiators: existing projects overlap substantially, including replay and practice. Present the personal benefit and the working implementation honestly; do not claim novelty or superiority without evidence.

Final checklist:

- [ ] Native plugin loads from a fresh checkout with documented versions/configuration.
- [ ] Automatic recording is real; unsupported input is rejected visibly or safely skipped.
- [ ] Tests pass, including original replay, unsafe proposals, and both register-comparison policies.
- [ ] README documents the grammar, privacy, setup, limits, and all commands.
- [ ] Real Modal usage is demonstrated without exposing a key or private code.
- [ ] Repository preserves licenses and attribution and contains no secrets.
- [ ] Screenshot and video exist; prerecorded fallbacks are labeled.
- [ ] Submission includes repository, image, demo instructions, honest limits, and prize selections.

**Start here:** get one automatically captured episode to replay its original inputs correctly. Then make one shorter candidate reach the same checked target. Everything else supports that loop.
