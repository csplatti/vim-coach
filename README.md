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
and cloud analysis disabled. Step 1 provides the setup, configuration, and
public command surface; automatic recording is implemented in the next step.

Available commands:

```text
:VimCoachPause
:VimCoachResume
:VimCoachStatus
:VimCoachLesson
:VimCoachPractice
:VimCoachResetData
```
