local M = {}

local defaults = {
  enabled = true,
  cloud_enabled = false,
  idle_ms = 1000,
  cooldown_ms = 60000,
  max_lines = 100,
  max_buffer_bytes = 8192,
  max_episode_keys = 128,
  max_episode_ms = 10000,
  max_candidates = 3,
  provider_timeout_ms = 10000,
  replay_timeout_ms = 1000,
}

local state = {
  config = vim.deepcopy(defaults),
  paused = false,
  setup_complete = false,
}

local function notify(message, level)
  vim.notify("Vim Coach: " .. message, level or vim.log.levels.INFO)
end

function M.setup(opts)
  state.config = vim.tbl_deep_extend("force", vim.deepcopy(defaults), opts or {})
  state.paused = not state.config.enabled
  state.setup_complete = true

  vim.g.vim_coach_enabled = state.config.enabled
  vim.g.vim_coach_cloud_enabled = state.config.cloud_enabled

  notify(state.config.enabled and "ready (automatic capture is next)" or "disabled")
end

function M.pause()
  state.paused = true
  vim.g.vim_coach_enabled = false
  notify("paused")
end

function M.resume()
  state.paused = false
  vim.g.vim_coach_enabled = true
  notify("resumed")
end

function M.status()
  local config = state.config
  local enabled = config.enabled and not state.paused
  local lines = {
    "Vim Coach status",
    "  capture: " .. (enabled and "enabled" or "paused"),
    "  cloud analysis: " .. (config.cloud_enabled and "enabled" or "disabled"),
    "  idle boundary: " .. tostring(config.idle_ms) .. " ms",
    "  setup: " .. (state.setup_complete and "complete" or "not called"),
    "  recorder: not implemented yet",
  }
  vim.notify(table.concat(lines, "\n"), vim.log.levels.INFO)
end

function M.lesson()
  notify("no lesson is available yet")
end

function M.practice()
  notify("practice mode is not implemented yet")
end

function M.reset_data()
  notify("no local data exists yet")
end

return M
