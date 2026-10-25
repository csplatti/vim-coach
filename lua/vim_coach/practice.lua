local M = {}

local state = {
  config = nil,
  episode = nil,
  buffer = nil,
  window = nil,
}

local function notify(message, level)
  vim.notify("Vim Coach: " .. message, level or vim.log.levels.INFO)
end

local function set_buffer_state(snapshot)
  if not state.buffer or not vim.api.nvim_buf_is_valid(state.buffer) then
    return
  end

  vim.bo[state.buffer].modifiable = true
  vim.api.nvim_buf_set_lines(state.buffer, 0, -1, false, snapshot.lines)
  pcall(function()
    vim.bo[state.buffer].endofline = snapshot.finalNewline == true
  end)

  if state.window and vim.api.nvim_win_is_valid(state.window) then
    local cursor = snapshot.cursor
    local row = math.max(1, math.min(cursor.row1Based, vim.api.nvim_buf_line_count(state.buffer)))
    local line = vim.api.nvim_buf_get_lines(state.buffer, row - 1, row, false)[1] or ""
    local col = math.max(0, math.min(cursor.byteColumn0Based, #line))
    vim.api.nvim_win_set_cursor(state.window, { row, col })
  end
end

local function capture_current()
  local cursor = vim.api.nvim_win_get_cursor(state.window)
  return {
    lines = vim.api.nvim_buf_get_lines(state.buffer, 0, -1, false),
    finalNewline = vim.bo[state.buffer].endofline == true,
    cursor = {
      row1Based = cursor[1],
      byteColumn0Based = cursor[2],
    },
    mode = vim.api.nvim_get_mode().mode,
  }
end

local function same(left, right)
  local text_equal = left.finalNewline == right.finalNewline and vim.deep_equal(left.lines, right.lines)
  local cursor_equal = vim.deep_equal(left.cursor, right.cursor)
  local mode_equal = left.mode == right.mode
  return text_equal, cursor_equal, mode_equal
end

function M.setup(config)
  state.config = config
end

function M.open(episode)
  if type(episode) ~= "table" or type(episode.before) ~= "table" or type(episode.after) ~= "table" then
    return false, "no captured episode is available for practice"
  end

  if state.window and vim.api.nvim_win_is_valid(state.window) then
    vim.api.nvim_set_current_win(state.window)
    return true
  end

  state.episode = episode
  vim.cmd("botright new")
  state.window = vim.api.nvim_get_current_win()
  state.buffer = vim.api.nvim_get_current_buf()
  vim.bo[state.buffer].buftype = "nofile"
  vim.bo[state.buffer].bufhidden = "wipe"
  vim.bo[state.buffer].swapfile = false
  vim.bo[state.buffer].filetype = "vimcoach-practice"
  vim.b[state.buffer].vim_coach_practice = true
  vim.api.nvim_buf_set_name(state.buffer, "[Vim Coach Practice " .. tostring(episode.id) .. "]")

  set_buffer_state(episode.before)
  notify("practice opened; edit the scratch buffer, then run :VimCoachPracticeCheck")
  return true
end

function M.check()
  if not state.episode or not state.window or not vim.api.nvim_win_is_valid(state.window) then
    return false, "no practice buffer is open"
  end

  local current = capture_current()
  local text_equal, cursor_equal, mode_equal = same(current, state.episode.after)
  if text_equal and cursor_equal and mode_equal then
    notify("practice complete: scratch state matches the captured target")
    return true
  end

  local differences = {}
  if not text_equal then
    differences[#differences + 1] = "buffer text"
  end
  if not cursor_equal then
    differences[#differences + 1] = "cursor"
  end
  if not mode_equal then
    differences[#differences + 1] = "mode"
  end
  notify("practice not complete; mismatch in " .. table.concat(differences, ", "), vim.log.levels.WARN)
  return false
end

function M.reset()
  if not state.episode or not state.window or not vim.api.nvim_win_is_valid(state.window) then
    return false, "no practice buffer is open"
  end
  set_buffer_state(state.episode.before)
  notify("practice reset to the captured starting state")
  return true
end

function M.close()
  if state.window and vim.api.nvim_win_is_valid(state.window) then
    vim.api.nvim_win_close(state.window, true)
  end
  state.window = nil
  state.buffer = nil
  state.episode = nil
end

function M.status()
  return {
    open = state.window ~= nil and vim.api.nvim_win_is_valid(state.window),
    episodeId = state.episode and state.episode.id or nil,
  }
end

return M
