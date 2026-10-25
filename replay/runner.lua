-- Fixed, data-only replay harness. It receives JSON on stdin and emits one
-- JSON result on stdout. It never evaluates input as Lua or Ex commands.

vim.opt.rtp:prepend(vim.fn.getcwd())
vim.o.loadplugins = false
vim.o.modeline = false
vim.o.swapfile = false
vim.o.backup = false
vim.o.writebackup = false
vim.o.undofile = false
vim.o.shadafile = "NONE"

local grammar = require("vim_coach.grammar")

local function finish(result)
  io.write(vim.fn.json_encode(result) .. "\n")
  io.flush()
  vim.cmd("qa!")
end

local function fail(message)
  finish({ schemaVersion = 1, ok = false, error = message })
end

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

local function snapshot()
  local bufnr = vim.api.nvim_get_current_buf()
  local winid = vim.api.nvim_get_current_win()
  local cursor = vim.api.nvim_win_get_cursor(winid)
  local version = vim.version()
  local registers = {}
  for _, name in ipairs({ '"', "-", "1", "2", "3", "4", "5", "6", "7", "8", "9" }) do
    registers[name] = capture_register(name)
  end

  return {
    lines = vim.api.nvim_buf_get_lines(bufnr, 0, -1, false),
    finalNewline = vim.bo[bufnr].endofline == true,
    bufferId = bufnr,
    cursor = {
      row1Based = cursor[1],
      byteColumn0Based = cursor[2],
    },
    mode = vim.api.nvim_get_mode().mode,
    relevantOptions = {
      iskeyword = vim.bo[bufnr].iskeyword,
      fileformat = vim.bo[bufnr].fileformat,
      virtualedit = vim.wo[winid].virtualedit,
      selection = vim.o.selection,
      whichwrap = vim.o.whichwrap,
    },
    trackedRegisters = registers,
    profileId = string.format("nvim-%d.%d.%d", version.major, version.minor, version.patch),
  }
end

local function apply_register(name, value)
  if type(value) ~= "table" then
    return
  end
  local contents = value.contents or {}
  local regtype = value.type or ""
  if #contents == 0 then
    contents = ""
  end
  pcall(vim.fn.setreg, name, contents, regtype)
end

local function prepare(before)
  if type(before) ~= "table" or type(before.lines) ~= "table" then
    return false, "before snapshot is malformed"
  end

  vim.cmd("enew")
  local bufnr = vim.api.nvim_get_current_buf()
  vim.bo[bufnr].modifiable = true
  vim.api.nvim_buf_set_lines(bufnr, 0, -1, false, #before.lines > 0 and before.lines or { "" })

  if before.finalNewline ~= nil then
    pcall(function()
      vim.bo[bufnr].endofline = before.finalNewline == true
    end)
  end

  local options = before.relevantOptions or {}
  for name, value in pairs({
    iskeyword = options.iskeyword,
    fileformat = options.fileformat,
  }) do
    if value ~= nil then
      pcall(function()
        vim.bo[bufnr][name] = value
      end)
    end
  end
  if options.virtualedit ~= nil then
    pcall(function()
      vim.wo[0].virtualedit = options.virtualedit
    end)
  end
  if options.selection ~= nil then
    vim.o.selection = options.selection
  end
  if options.whichwrap ~= nil then
    vim.o.whichwrap = options.whichwrap
  end

  for name, value in pairs(before.trackedRegisters or {}) do
    apply_register(name, value)
  end

  local cursor = before.cursor or {}
  local row = math.max(1, tonumber(cursor.row1Based) or 1)
  local col = math.max(0, tonumber(cursor.byteColumn0Based) or 0)
  local line_count = vim.api.nvim_buf_line_count(bufnr)
  row = math.min(row, line_count)
  local line = vim.api.nvim_buf_get_lines(bufnr, row - 1, row, false)[1] or ""
  col = math.min(col, #line)
  vim.api.nvim_win_set_cursor(0, { row, col })
  vim.cmd("normal! \27")
  return true, nil
end

local function main()
  local input = io.read("*a")
  local ok, payload = pcall(vim.fn.json_decode, input or "")
  if not ok or type(payload) ~= "table" then
    return fail("input is not valid JSON")
  end
  if payload.schemaVersion ~= 1 then
    return fail("unsupported schema version")
  end
  if type(payload.tokens) ~= "table" then
    return fail("tokens must be an array")
  end

  local valid, reason = grammar.validate(payload.tokens)
  if not valid then
    return fail("unsafe or incomplete token sequence: " .. reason)
  end

  local prepared, prepare_reason = prepare(payload.before)
  if not prepared then
    return fail(prepare_reason)
  end

  vim.api.nvim_feedkeys(table.concat(payload.tokens), "xt", false)
  vim.wait(10)
  finish({ schemaVersion = 1, ok = true, state = snapshot() })
end

local ok, err = xpcall(main, debug.traceback)
if not ok then
  fail(tostring(err))
end
