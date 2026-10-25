local M = {}
local recorder = require("vim_coach.recorder")

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

  if state.config.enabled then
    recorder.setup(state.config, function(episode)
      notify(string.format(
        "captured episode %d (%d logical keys); awaiting verification",
        episode.id,
        episode.originalLogicalKeyCount
      ))
    end)
  else
    recorder.stop("disabled in configuration")
  end

  notify(state.config.enabled and "ready" or "disabled")
end

function M.pause()
  state.paused = true
  vim.g.vim_coach_enabled = false
  recorder.pause()
  notify("paused")
end

function M.resume()
  state.paused = false
  vim.g.vim_coach_enabled = true
  recorder.resume()
  notify("resumed")
end

function M.status()
  local config = state.config
  local enabled = config.enabled and not state.paused
  local recorder_status = recorder.status()
  local episode = recorder_status.episode
  local lines = {
    "Vim Coach status",
    "  capture: " .. (enabled and "enabled" or "paused"),
    "  cloud analysis: " .. (config.cloud_enabled and "enabled" or "disabled"),
    "  idle boundary: " .. tostring(config.idle_ms) .. " ms",
    "  setup: " .. (state.setup_complete and "complete" or "not called"),
    "  recorder health: " .. (recorder_status.healthy and "healthy" or "disabled after error"),
    "  recorder active: " .. (recorder_status.started and "yes" or "no"),
    "  last skip: " .. tostring(episode.lastSkipReason),
    "  last episode: " .. (episode.lastEpisodeId and (
      tostring(episode.lastEpisodeId) .. " (" .. tostring(episode.lastEpisodeKeys) .. " logical keys)"
    ) or "none"),
  }
  if recorder_status.lastError then
    table.insert(lines, "  recorder error: " .. recorder_status.lastError)
  end
  vim.notify(table.concat(lines, "\n"), vim.log.levels.INFO)
end

function M.lesson()
  notify("no lesson is available yet")
end

function M.practice()
  notify("practice mode is not implemented yet")
end

function M.reset_data()
  recorder.reset()
  notify("local in-memory episode data cleared")
end

return M
