local progress = require("vim_coach.progress")

local M = {}

local state = {
  buffer = nil,
  line_goals = {},
}

local function binding(goal)
  return table.concat(goal.binding or {}, "")
end

local function status_icon(goal)
  if goal.status == "completed" then
    return "✓"
  end
  if goal.status == "paused" then
    return "Ⅱ"
  end
  return "›"
end

local function render()
  if not state.buffer or not vim.api.nvim_buf_is_valid(state.buffer) then
    return
  end
  progress.sync_lessons()
  local all = progress.goals()
  table.sort(all, function(left, right)
    local order = { active = 1, paused = 2, completed = 3 }
    local left_order = order[left.status] or 4
    local right_order = order[right.status] or 4
    if left_order ~= right_order then
      return left_order < right_order
    end
    return left.title < right.title
  end)

  local lines = {
    " Vim Coach Goals",
    "",
  }
  state.line_goals = {}
  if #all == 0 then
    lines[#lines + 1] = " No goals yet. Review a lesson to begin."
  else
    for _, goal in ipairs(all) do
      local line = string.format(
        " %s %3d / %-3d  %-8s %s",
        status_icon(goal),
        goal.progress or 0,
        goal.target or 0,
        binding(goal),
        goal.title or goal.featureId
      )
      lines[#lines + 1] = line
      state.line_goals[#lines] = goal.featureId
    end
  end
  lines[#lines + 1] = ""
  lines[#lines + 1] = " j/k navigate  Enter details  x pause/resume  r refresh  q close"

  vim.bo[state.buffer].modifiable = true
  vim.api.nvim_buf_set_lines(state.buffer, 0, -1, false, lines)
  vim.bo[state.buffer].modifiable = false
end

local function selected_goal()
  local row = vim.api.nvim_win_get_cursor(0)[1]
  local feature_id = state.line_goals[row]
  if not feature_id then
    return nil
  end
  for _, goal in ipairs(progress.goals()) do
    if goal.featureId == feature_id then
      return goal
    end
  end
  return nil
end

local function map(lhs, callback)
  vim.keymap.set("n", lhs, callback, { buffer = state.buffer, silent = true, nowait = true })
end

function M.open()
  vim.cmd("botright new")
  state.buffer = vim.api.nvim_get_current_buf()
  vim.api.nvim_buf_set_name(state.buffer, "vim-coach://goals")
  vim.bo[state.buffer].buftype = "nofile"
  vim.bo[state.buffer].bufhidden = "wipe"
  vim.bo[state.buffer].swapfile = false
  vim.bo[state.buffer].filetype = "vimcoach"
  vim.bo[state.buffer].modifiable = false

  map("q", function()
    vim.api.nvim_win_close(0, true)
  end)
  map("r", render)
  map("x", function()
    local goal = selected_goal()
    if not goal then
      return
    end
    local ok, result = progress.toggle(goal.featureId)
    if not ok then
      vim.notify("Vim Coach: " .. result, vim.log.levels.WARN)
    end
    render()
  end)
  map("<CR>", function()
    local goal = selected_goal()
    if not goal then
      return
    end
    vim.notify(string.format(
      "Vim Coach: %s (%s) — %d of %d uses, %s",
      goal.title,
      binding(goal),
      goal.progress or 0,
      goal.target or 0,
      goal.status
    ))
  end)

  render()
  vim.api.nvim_win_set_cursor(0, { #progress.goals() > 0 and 3 or 1, 0 })
end

return M
