local M = {}

local commands = {
  { ":VimCoachStatus", "Show capture, analysis, queue, and recorder status" },
  { ":VimCoachPause", "Pause recording and automatic analysis" },
  { ":VimCoachResume", "Resume recording and automatic analysis" },
  { ":VimCoachSync", "Retry queued episodes or send them manually" },
  { ":VimCoachAnalyze", "Alias for :VimCoachSync" },
  { ":VimCoachLesson", "Show how many verified lessons are ready" },
  { ":VimCoachGoals", "Open learning goals and practice progress" },
  { ":VimCoachStats", "Open learned-feature statistics" },
  { ":VimCoachPractice", "Practice the latest captured edit in a scratch buffer" },
  { ":VimCoachPracticeCheck", "Check the open practice buffer" },
  { ":VimCoachPracticeReset", "Restore the open practice buffer" },
  { ":VimCoachDismiss", "Dismiss the current legacy inline lesson" },
  { ":VimCoachKnow", "Suppress the current legacy inline concept" },
  { ":VimCoachResetData", "Clear queued in-memory episodes" },
  { ":VimCoachResetProfile", "Confirm and erase lessons, goals, and progress" },
  { ":VimCoachResetProfile!", "Erase the profile without confirmation" },
  { ":VimCoachHelp", "Open this command guide" },
}

function M.open()
  local lines = {
    " Vim Coach Help",
    "",
    " Vim Coach records supported keystroke sequences and analyzes them",
    " automatically. You normally do not need to run a sync command.",
    "",
    " Commands",
  }

  for _, item in ipairs(commands) do
    lines[#lines + 1] = string.format(" %-27s %s", item[1], item[2])
  end

  lines[#lines + 1] = ""
  lines[#lines + 1] = " q close"

  vim.cmd("botright new")
  local buffer = vim.api.nvim_get_current_buf()
  vim.api.nvim_buf_set_name(buffer, "vim-coach://help")
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
