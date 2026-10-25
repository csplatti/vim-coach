local progress = require("vim_coach.progress")

local M = {}

function M.open()
  progress.sync_lessons()
  local goals = progress.goals()
  local active = 0
  local paused = 0
  local learned = 0
  local uses = 0
  local completed = {}
  for _, goal in ipairs(goals) do
    uses = uses + (goal.progress or 0)
    if goal.status == "active" then
      active = active + 1
    elseif goal.status == "paused" then
      paused = paused + 1
    elseif goal.status == "completed" then
      learned = learned + 1
      completed[#completed + 1] = goal
    end
  end
  table.sort(completed, function(left, right)
    return (left.completedAt or "") > (right.completedAt or "")
  end)

  local lines = {
    " Vim Coach Stats",
    "",
    string.format(" %d feature%s learned", learned, learned == 1 and "" or "s"),
    string.format(" %d active goal%s", active, active == 1 and "" or "s"),
    string.format(" %d paused goal%s", paused, paused == 1 and "" or "s"),
    string.format(" %d tracked successful use%s", uses, uses == 1 and "" or "s"),
    "",
    " Recently learned",
  }
  if #completed == 0 then
    lines[#lines + 1] = " Nothing yet — active goals will appear here when completed."
  else
    for index, goal in ipairs(completed) do
      if index > 8 then
        break
      end
      lines[#lines + 1] = string.format(
        " ✓ %-8s %s%s",
        table.concat(goal.binding or {}, ""),
        goal.title or goal.featureId,
        goal.completedAt and ("  " .. goal.completedAt:sub(1, 10)) or ""
      )
    end
  end
  lines[#lines + 1] = ""
  lines[#lines + 1] = " q close"

  vim.cmd("botright new")
  local buffer = vim.api.nvim_get_current_buf()
  vim.api.nvim_buf_set_name(buffer, "vim-coach://stats")
  vim.bo[buffer].buftype = "nofile"
  vim.bo[buffer].bufhidden = "wipe"
  vim.bo[buffer].swapfile = false
  vim.bo[buffer].filetype = "vimcoach"
  vim.api.nvim_buf_set_lines(buffer, 0, -1, false, lines)
  vim.bo[buffer].modifiable = false
  vim.keymap.set("n", "q", function()
    vim.api.nvim_win_close(0, true)
  end, { buffer = buffer, silent = true, nowait = true })
end

return M
