if vim.g.loaded_vim_coach == 1 then
  return
end

vim.g.loaded_vim_coach = 1

local coach = require("vim_coach")

local function command(name, callback, description)
  vim.api.nvim_create_user_command(name, callback, {
    desc = description,
  })
end

command("VimCoachPause", function()
  coach.pause()
end, "Pause Vim Coach recording")

command("VimCoachResume", function()
  coach.resume()
end, "Resume Vim Coach recording")

command("VimCoachStatus", function()
  coach.status()
end, "Show Vim Coach status")

command("VimCoachLesson", function()
  coach.lesson()
end, "Open the available Vim Coach lesson")

command("VimCoachPractice", function()
  coach.practice()
end, "Open the Vim Coach practice buffer")

command("VimCoachResetData", function()
  coach.reset_data()
end, "Reset local Vim Coach data")
