local M = {}
local recorder = require("vim_coach.recorder")
local ui = require("vim_coach.ui")
local practice = require("vim_coach.practice")
local worker = require("vim_coach.worker")
local queue = require("vim_coach.queue")
local progress = require("vim_coach.progress")
local goals = require("vim_coach.goals")
local stats = require("vim_coach.stats")
local help = require("vim_coach.help")

local defaults = {
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
  provider_timeout_ms = 10000,
  replay_timeout_ms = 1000,
  debug_prompt = false,
  goal_target = 50,
}

local state = {
  config = vim.deepcopy(defaults),
  paused = false,
  setup_complete = false,
  active_batch = nil,
}

local function notify(message, level)
  vim.notify("Vim Coach: " .. message, level or vim.log.levels.INFO)
end

local pump_queue

function M.setup(opts)
  state.config = vim.tbl_deep_extend("force", vim.deepcopy(defaults), opts or {})
  state.paused = not state.config.enabled
  state.setup_complete = true
  state.active_batch = nil
  queue.setup(state.config)
  ui.setup(state.config)
  practice.setup(state.config)
  progress.setup(state.config)
  worker.setup(state.config, function(result, error_message)
    local batch = state.active_batch or {}
    state.active_batch = nil
    if error_message then
      notify("batch failed: " .. error_message .. "; episodes kept for retry", vim.log.levels.WARN)
      return
    end
    queue.remove_ids(vim.tbl_map(function(episode)
      return episode.id
    end, batch))
    queue.add_lessons(result.suggestions or {}, batch)
    local lessons = 0
    for _, suggestion in ipairs(result.suggestions or {}) do
      lessons = lessons + #(suggestion.candidates or {})
    end
    if lessons > 0 then
      notify(string.format("batch complete; %d verified lesson%s ready", lessons, lessons == 1 and " is" or "s are"))
    elseif result.providerReturnedContent == false then
      notify("batch complete; provider emitted no final JSON", vim.log.levels.WARN)
    elseif (result.providerCandidateCount or 0) == 0 then
      notify("batch complete; model proposed no candidates")
    else
      notify(string.format(
        "batch complete; model proposed %d candidate%s, but local replay rejected all",
        result.providerCandidateCount,
        result.providerCandidateCount == 1 and "" or "s"
      ), vim.log.levels.WARN)
    end
    vim.schedule(function()
      pump_queue(false)
    end)
  end)

  vim.g.vim_coach_enabled = state.config.enabled
  vim.g.vim_coach_cloud_enabled = state.config.cloud_enabled

  if state.config.enabled then
    recorder.setup(state.config, function(episode)
      notify(string.format(
        "queued episode %d (%d logical keys); automatic analysis pending",
        episode.id,
        episode.originalLogicalKeyCount
      ))
      local ok, reason = queue.enqueue(episode)
      if not ok and reason then
        notify(reason, vim.log.levels.WARN)
        return
      end
      vim.schedule(function()
        pump_queue(false)
      end)
    end, function(tokens)
      local completed = progress.record_tokens(tokens)
      for _, goal in ipairs(completed) do
        notify(string.format("goal complete: %s (%s)", goal.title, table.concat(goal.binding or {}, "")))
      end
    end)
  else
    worker.cancel()
    recorder.stop("disabled in configuration")
  end

  notify(state.config.enabled and "ready" or "disabled")
end

function M.pause()
  state.paused = true
  vim.g.vim_coach_enabled = false
  recorder.pause()
  worker.cancel()
  state.active_batch = nil
  notify("paused")
end

function M.resume()
  state.paused = false
  vim.g.vim_coach_enabled = true
  recorder.resume()
  vim.schedule(function()
    pump_queue(false)
  end)
  notify("resumed")
end

function M.status()
  local config = state.config
  local enabled = config.enabled and not state.paused
  local recorder_status = recorder.status()
  local ui_status = ui.status()
  local practice_status = practice.status()
  local queue_status = queue.status()
  local worker_status = worker.status()
  local episode = recorder_status.episode
  local lines = {
    "Vim Coach status",
    "  capture: " .. (enabled and "enabled" or "paused"),
    "  cloud analysis: " .. (config.cloud_enabled and "enabled" or "disabled"),
    "  pending batch episodes: " .. tostring(queue_status.pending),
    "  verified review lessons: " .. tostring(queue_status.lessons),
    "  batch worker: " .. (worker_status.active and "running" or "idle"),
    "  idle boundary: " .. tostring(config.idle_ms) .. " ms",
    "  setup: " .. (state.setup_complete and "complete" or "not called"),
    "  recorder health: " .. (recorder_status.healthy and "healthy" or "disabled after error"),
    "  recorder active: " .. (recorder_status.started and "yes" or "no"),
    "  last skip: " .. tostring(episode.lastSkipReason),
    "  last episode: " .. (episode.lastEpisodeId and (
      tostring(episode.lastEpisodeId) .. " (" .. tostring(episode.lastEpisodeKeys) .. " logical keys)"
    ) or "none"),
    "  inline lesson card: " .. (ui_status.available and "legacy available" or "none"),
    "  practice: " .. (practice_status.open and "open" or "closed"),
  }
  if recorder_status.lastError then
    table.insert(lines, "  recorder error: " .. recorder_status.lastError)
  end
  vim.notify(table.concat(lines, "\n"), vim.log.levels.INFO)
end

function M.lesson()
  local count = queue.status().lessons
  notify(string.format("%d verified lesson%s ready; use :VimCoachGoals to track practice", count, count == 1 and " is" or "s are"))
end

function M.show_suggestion(proposal)
  local ok, reason = ui.show(proposal)
  if not ok then
    notify(reason, vim.log.levels.WARN)
  end
  return ok
end

function M.dismiss()
  local ok, reason = ui.dismiss(false)
  if not ok then
    notify(reason)
  end
end

function M.know()
  local ok, reason = ui.dismiss(true)
  if not ok then
    notify(reason)
  end
end

function pump_queue(manual)
  if not state.config.cloud_enabled then
    if manual then
      notify("cloud analysis is disabled")
    end
    return false
  end
  if state.paused or state.active_batch or worker.status().active then
    if manual and (state.active_batch or worker.status().active) then
      notify("a batch is already running; new episodes will follow automatically")
    end
    return false
  end
  local pending = queue.pending()
  if #pending == 0 then
    if manual then
      notify("no queued episodes are ready to sync")
    end
    return false
  end
  state.active_batch = pending
  local ok, reason = worker.request_batch(pending)
  if not ok then
    state.active_batch = nil
    notify(reason, vim.log.levels.WARN)
    return false
  end
  if manual then
    notify(string.format(
      "sent %d episode%s for analysis",
      #pending,
      #pending == 1 and "" or "s"
    ))
  end
  return true
end

function M.sync()
  pump_queue(true)
end

function M.analyze()
  M.sync()
end

function M.practice()
  local ok, reason = practice.open(recorder.last_episode())
  if not ok then
    notify(reason)
  end
end

function M.practice_check()
  local ok, reason = practice.check()
  if not ok and reason then
    notify(reason)
  end
end

function M.practice_reset()
  local ok, reason = practice.reset()
  if not ok and reason then
    notify(reason)
  end
end

function M.goals()
  goals.open()
end

function M.stats()
  stats.open()
end

function M.help()
  help.open()
end

function M.reset_data()
  worker.cancel()
  state.active_batch = nil
  recorder.reset()
  queue.clear()
  ui.reset()
  practice.close()
  notify("local in-memory episode data cleared")
end

function M.reset_profile(force)
  if not force then
    local choice = vim.fn.confirm(
      "Reset all Vim Coach lessons, goals, and progress? This cannot be undone.",
      "&Reset\n&Cancel",
      2
    )
    if choice ~= 1 then
      notify("profile reset cancelled")
      return false
    end
  end

  worker.cancel()
  state.active_batch = nil
  recorder.reset()
  queue.clear()
  ui.reset()
  practice.close()
  local ok, reason = progress.reset_profile()
  if not ok then
    notify("profile reset failed: " .. tostring(reason), vim.log.levels.ERROR)
    return false
  end
  notify("profile reset; lessons, goals, and progress cleared")
  return true
end

return M
