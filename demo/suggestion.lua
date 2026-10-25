-- Offline UI demo. It uses a locally declared verified result and makes no
-- provider request. Run from the repository root with:
--   nvim -u demo/suggestion.lua

dofile("demo/minimal.lua")

require("vim_coach").show_suggestion({
  originalTokens = { "w", "w", "w", "x" },
  originalLogicalKeys = 4,
  candidate = {
    compiledTokens = { "3", "w", "x" },
    concept = "counted-movement",
    explanation = "Use a count instead of repeating the movement.",
  },
  candidateLogicalKeys = 3,
  savedLogicalKeys = 1,
  verification = {
    accepted = true,
    textEqual = true,
    cursorEqual = true,
    modeEqual = true,
    registersEqual = true,
  },
})
