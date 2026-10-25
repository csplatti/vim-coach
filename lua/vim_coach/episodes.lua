local grammar = require("vim_coach.grammar")
local snapshot = require("vim_coach.snapshot")

local M = {}

local state = {
  config = nil,
  current = nil,
  generation = 0,
  idle_timer = nil,
  suppression_timer = nil,
  suppressed = false,
  running = false,
  next_id = 1,
  last_skip_reason = "none",
  last_episode = nil,
  on_episode = nil,
  synthetic_tail = nil,
}

local function now_ns()
  return vim.loop.hrtime()
end

local function cancel_timer(timer)
  if timer then
    if type(timer) == "userdata" and timer.stop then
      pcall(timer.stop, timer)
    else
      pcall(vim.fn.timer_stop, timer)
    end
  end
end

local function cancel_idle_timer()
  cancel_timer(state.idle_timer)
  state.idle_timer = nil
end

local function cancel_suppression_timer()
  cancel_timer(state.suppression_timer)
  state.suppression_timer = nil
end

local function clear_current(reason)
  cancel_idle_timer()
  state.current = nil
  state.synthetic_tail = nil
  state.generation = state.generation + 1
  if reason then
    state.last_skip_reason = reason
  end
end

local function suppress_until_idle(reason)
  state.suppressed = true
  state.last_skip_reason = reason
  cancel_suppression_timer()
  state.suppression_timer = vim.defer_fn(function()
    state.suppressed = false
    state.suppression_timer = nil
  end, state.config.idle_ms)
end

local function mode_is_supported(mode)
  return mode == "n" or mode:sub(1, 2) == "no"
end

local function current_context_matches()
  if not state.current then
    return false
  end
  return state.current.buffer_id == vim.api.nvim_get_current_buf()
    and state.current.window_id == vim.api.nvim_get_current_win()
    and mode_is_supported(vim.api.nvim_get_mode().mode)
end

local function finish(generation)
  if not state.running or not state.current or generation ~= state.generation then
    return
  end

  state.idle_timer = nil
  if not current_context_matches() then
    clear_current("buffer, window, or mode changed before the idle boundary")
    return
  end

  if vim.api.nvim_get_mode().mode ~= "n" then
    clear_current("episode did not settle in Normal mode")
    return
  end

  local valid, reason = grammar.validate(state.current.resolved_tokens)
  if not valid then
    clear_current("unsupported or incomplete sequence: " .. reason)
    return
  end

  local after, snapshot_reason = snapshot.capture(
    state.current.buffer_id,
    state.current.window_id,
    state.config
  )
  if not after then
    clear_current(snapshot_reason)
    return
  end

  if snapshot.same_text(state.current.before, after) then
    clear_current("navigation without a text change")
    return
  end

  local episode = {
    id = state.next_id,
    generation = state.generation,
    before = state.current.before,
    after = after,
    typedTokens = state.current.typed_tokens,
    resolvedTokens = state.current.resolved_tokens,
    originalLogicalKeyCount = #state.current.resolved_tokens,
    startedAt = state.current.started_at,
    endedAt = now_ns(),
    provenanceFlags = state.current.provenance_flags,
  }
  state.next_id = state.next_id + 1
  state.last_episode = episode
  state.last_skip_reason = "none"
  state.current = nil

  if state.on_episode then
    state.on_episode(episode)
  end
end

local function schedule_finish()
  cancel_idle_timer()
  local generation = state.generation
  state.idle_timer = vim.defer_fn(function()
    finish(generation)
  end, state.config.idle_ms)
end

function M.setup(config, on_episode)
  state.config = config
  state.on_episode = on_episode
  state.running = true
  state.current = nil
  state.suppressed = false
  state.last_skip_reason = "none"
  state.synthetic_tail = nil
end

function M.stop(reason)
  state.running = false
  clear_current(reason or "recording stopped")
  cancel_suppression_timer()
end

function M.start()
  state.running = true
end

function M.reset()
  state.last_episode = nil
  state.last_skip_reason = "none"
end

function M.invalidate(reason)
  if state.current then
    clear_current(reason)
  end
end

function M.on_key(resolved, typed)
  if not state.running then
    return
  end

  -- In Neovim 0.9, normal-mode delete commands can emit an internal
  -- equivalent after the visible key (x -> d,l and D -> d,$). The callback
  -- reports those generated keys with no typed provenance. Consume only the
  -- exact known tails; never infer arbitrary input.
  if state.synthetic_tail and (typed == nil or typed == "") then
    if resolved == state.synthetic_tail[1] then
      table.remove(state.synthetic_tail, 1)
      if #state.synthetic_tail == 0 then
        state.synthetic_tail = nil
      end
      return
    end
    state.synthetic_tail = nil
  end

  local token, typed_token, resolved_token, reason = grammar.normalize(resolved, typed)
  if not token then
    if state.current then
      clear_current(reason)
    elseif vim.api.nvim_get_mode().mode == "n" then
      suppress_until_idle(reason)
    end
    return
  end

  local buffer_id = vim.api.nvim_get_current_buf()
  local window_id = vim.api.nvim_get_current_win()
  local mode = vim.api.nvim_get_mode().mode

  if state.current and not current_context_matches() then
    clear_current("buffer, window, or mode changed during capture")
    return
  end

  if not state.current then
    if state.suppressed or mode ~= "n" then
      return
    end

    local before, snapshot_reason = snapshot.capture(buffer_id, window_id, state.config)
    if not before then
      state.last_skip_reason = snapshot_reason
      suppress_until_idle(snapshot_reason)
      return
    end

    state.current = {
      buffer_id = buffer_id,
      window_id = window_id,
      before = before,
      typed_tokens = {},
      resolved_tokens = {},
      provenance_flags = {},
      started_at = now_ns(),
    }
  end

  table.insert(state.current.typed_tokens, typed_token)
  table.insert(state.current.resolved_tokens, resolved_token)
  if #state.current.resolved_tokens > state.config.max_episode_keys then
    clear_current("episode exceeds the key limit")
    return
  end

  local elapsed_ms = (now_ns() - state.current.started_at) / 1000000
  if elapsed_ms > state.config.max_episode_ms then
    clear_current("episode exceeds the time limit")
    return
  end

  if (typed == nil or typed == "") and token == "x" then
    state.synthetic_tail = { "d", "l" }
  elseif (typed == nil or typed == "") and token == "D" then
    state.synthetic_tail = { "d", "$" }
  end

  schedule_finish()
end

function M.status()
  local episode = state.last_episode
  return {
    active = state.running and state.current ~= nil,
    suppressed = state.suppressed,
    lastSkipReason = state.last_skip_reason,
    lastEpisodeId = episode and episode.id or nil,
    lastEpisodeKeys = episode and episode.originalLogicalKeyCount or nil,
  }
end

return M
