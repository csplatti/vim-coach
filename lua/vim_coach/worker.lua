local M = {}

local state = {
  config = nil,
  job = nil,
  generation = 0,
  on_result = nil,
}

local function notify(message, level)
  vim.notify("Vim Coach: " .. message, level or vim.log.levels.INFO)
end

function M.setup(config, on_result)
  state.config = config
  state.on_result = on_result
end

function M.cancel()
  state.generation = state.generation + 1
  if state.job then
    pcall(vim.fn.jobstop, state.job)
    state.job = nil
  end
end

function M.request(episode)
  if not state.config or not state.config.cloud_enabled then
    return false, "cloud analysis is disabled"
  end
  if type(episode) ~= "table" then
    return false, "no episode is available"
  end

  M.cancel()
  local generation = state.generation
  local command = state.config.worker_command or { "python3", "worker/main.py" }
  local worker_cwd = state.config.worker_cwd or vim.fn.getcwd()
  if not state.config.worker_command then
    local project_python = worker_cwd .. "/.venv-x86/bin/python"
    if vim.fn.filereadable(project_python) == 1 then
      command = { project_python, "worker/main.py" }
    else
      project_python = worker_cwd .. "/.venv/bin/python"
      if vim.fn.filereadable(project_python) == 1 then
        command = { project_python, "worker/main.py" }
      end
    end
  end
  local output = {}
  local job = vim.fn.jobstart(command, {
    cwd = worker_cwd,
    stdin = "pipe",
    stdout = "pipe",
    stderr = "pipe",
    env = { TMPDIR = "/private/tmp" },
    stdout_buffered = true,
    on_stdout = function(_, data)
      if data then
        for _, line in ipairs(data) do
          if line ~= "" then
            output[#output + 1] = line
          end
        end
      end
    end,
    on_exit = function(_, exit_code)
      if generation ~= state.generation then
        return
      end
      state.job = nil
      if exit_code ~= 0 then
        notify("analysis worker exited with code " .. tostring(exit_code), vim.log.levels.WARN)
        return
      end
      local ok, result = pcall(vim.fn.json_decode, table.concat(output, "\n"))
      if not ok or type(result) ~= "table" then
        notify("analysis worker returned malformed JSON", vim.log.levels.WARN)
        return
      end
      if result.ok ~= true then
        notify(result.error or "analysis worker failed", vim.log.levels.WARN)
        return
      end
      if result.episodeId ~= nil and result.episodeId ~= episode.id then
        return
      end
      if state.on_result then
        state.on_result(result)
      end
    end,
  })
  if job <= 0 then
    return false, "could not start analysis worker"
  end

  state.job = job
  local request = vim.fn.json_encode({
    schemaVersion = 1,
    cloudEnabled = true,
    episodeId = episode.id,
    episode = episode,
  })
  vim.fn.chansend(job, request)
  vim.fn.chanclose(job, "stdin")
  return true
end

function M.status()
  return { active = state.job ~= nil }
end

return M
