-- Minimal development profile for Vim Coach.
-- Run from the repository root with:
--   nvim -u demo/minimal.lua

local source = debug.getinfo(1, "S").source:sub(2)
local repo_root = vim.fn.fnamemodify(source, ":h:h")

vim.opt.rtp:prepend(repo_root)
if vim.fn.isdirectory("/private/tmp") == 1 then
  vim.env.TMPDIR = "/private/tmp"
end

require("vim_coach").setup({
  enabled = true,
  cloud_enabled = vim.env.VIM_COACH_CLOUD == "1",
  idle_ms = 1000,
  cooldown_ms = 60000,
  max_lines = 100,
  max_buffer_bytes = 8192,
  max_episode_keys = 128,
  max_episode_ms = 10000,
  max_candidates = 3,
  provider_timeout_ms = 10000,
  replay_timeout_ms = 1000,
  worker_cwd = repo_root,
})
