local episodes = require("vim_coach.episodes")

local M = {}

local state = {
  namespace = vim.api.nvim_create_namespace("vim_coach_recorder"),
  augroup = nil,
  initialized = false,
  started = false,
  healthy = true,
  last_error = nil,
  config = nil,
}

local function disable_after_error(message)
  state.healthy = false
  state.last_error = message
  state.started = false
  pcall(vim.on_key, nil, state.namespace)
  episodes.stop("recorder callback failed")
  vim.schedule(function()
    vim.notify("Vim Coach recorder disabled: " .. message, vim.log.levels.ERROR)
  end)
end

local function on_key(resolved, typed)
  local ok, err = pcall(episodes.on_key, resolved, typed)
  if not ok then
    disable_after_error(tostring(err))
  end
  return nil
end

local function install_autocmds()
  if state.augroup then
    pcall(vim.api.nvim_del_augroup_by_id, state.augroup)
  end

  state.augroup = vim.api.nvim_create_augroup("VimCoachRecorder", { clear = true })
  vim.api.nvim_create_autocmd({ "BufLeave", "WinLeave", "FocusLost", "CmdlineEnter", "RecordingEnter" }, {
    group = state.augroup,
    callback = function(args)
      episodes.invalidate("capture interrupted by " .. args.event)
    end,
  })
end

function M.setup(config, on_episode)
  state.config = config
  state.healthy = true
  state.last_error = nil
  state.initialized = true
  install_autocmds()
  episodes.setup(config, on_episode)
  M.start()
end

function M.start()
  if not state.initialized or not state.healthy then
    return false
  end

  local ok, err = pcall(vim.on_key, on_key, state.namespace)
  if not ok then
    disable_after_error(tostring(err))
    return false
  end

  state.started = true
  episodes.start()
  return true
end

function M.stop(reason)
  pcall(vim.on_key, nil, state.namespace)
  state.started = false
  episodes.stop(reason)
end

function M.pause()
  M.stop("paused by user")
end

function M.resume()
  return M.start()
end

function M.reset()
  episodes.reset()
end

function M.status()
  local episode_status = episodes.status()
  return {
    healthy = state.healthy,
    started = state.started,
    lastError = state.last_error,
    episode = episode_status,
  }
end

function M.last_episode()
  return episodes.last_episode()
end

return M
