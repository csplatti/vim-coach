local M = {}

local register_names = { '"', "-", "1", "2", "3", "4", "5", "6", "7", "8", "9" }

local function capture_register(name)
  local ok, info = pcall(vim.fn.getreginfo, name)
  if not ok or type(info) ~= "table" then
    return { contents = {}, type = "" }
  end

  return {
    contents = vim.deepcopy(info.regcontents or {}),
    type = info.regtype or "",
  }
end

local function profile_id()
  local version = vim.version()
  return string.format("nvim-%d.%d.%d", version.major, version.minor, version.patch)
end

local function buffer_size(lines, final_newline)
  local size = 0
  for _, line in ipairs(lines) do
    size = size + #line
  end
  size = size + math.max(0, #lines - 1)
  if final_newline then
    size = size + 1
  end
  return size
end

local function get_final_newline(bufnr)
  local ok, value = pcall(function()
    return vim.bo[bufnr].endofline
  end)
  return ok and value == true or false
end

function M.capture(bufnr, winid, config)
  if not vim.api.nvim_buf_is_valid(bufnr) then
    return nil, "buffer is no longer valid"
  end
  if not vim.api.nvim_win_is_valid(winid) then
    return nil, "window is no longer valid"
  end
  if vim.bo[bufnr].buftype ~= "" then
    return nil, "buffer is not an ordinary file buffer"
  end
  if not vim.bo[bufnr].modifiable then
    return nil, "buffer is not modifiable"
  end
  if vim.b[bufnr].vim_coach_practice then
    return nil, "practice buffer is excluded"
  end

  local ok, lines = pcall(vim.api.nvim_buf_get_lines, bufnr, 0, -1, false)
  if not ok then
    return nil, "could not read buffer"
  end
  if #lines > config.max_lines then
    return nil, "buffer exceeds the line limit"
  end

  local final_newline = get_final_newline(bufnr)
  local byte_count = buffer_size(lines, final_newline)
  if byte_count > config.max_buffer_bytes then
    return nil, "buffer exceeds the byte limit"
  end

  local cursor = vim.api.nvim_win_get_cursor(winid)
  local options = {
    iskeyword = vim.bo[bufnr].iskeyword,
    fileformat = vim.bo[bufnr].fileformat,
    virtualedit = vim.wo[winid].virtualedit,
    selection = vim.o.selection,
    whichwrap = vim.o.whichwrap,
  }

  local registers = {}
  for _, name in ipairs(register_names) do
    registers[name] = capture_register(name)
  end

  return {
    lines = lines,
    finalNewline = final_newline,
    bufferId = bufnr,
    changedtick = vim.api.nvim_buf_get_changedtick(bufnr),
    cursor = {
      row1Based = cursor[1],
      byteColumn0Based = cursor[2],
    },
    mode = vim.api.nvim_get_mode().mode,
    relevantOptions = options,
    trackedRegisters = registers,
    profileId = profile_id(),
  }, nil
end

function M.same_text(left, right)
  return left.finalNewline == right.finalNewline and vim.deep_equal(left.lines, right.lines)
end

return M
