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

command("VimCoachHelp", function()
  coach.help()
end, "Show all Vim Coach commands")

command("VimCoachAnalyze", function()
  coach.analyze()
end, "Analyze the latest captured episode")

command("VimCoachSync", function()
  coach.sync()
end, "Retry or manually send queued Vim Coach episodes")

command("VimCoachLesson", function()
  coach.lesson()
end, "Show the Vim Coach review inbox status")

command("VimCoachGoals", function()
  coach.goals()
end, "Open Vim Coach learning goals")

command("VimCoachStats", function()
  coach.stats()
end, "Open Vim Coach learning statistics")

command("VimCoachDismiss", function()
  coach.dismiss()
end, "Dismiss the current Vim Coach lesson")

command("VimCoachKnow", function()
  coach.know()
end, "Suppress the current Vim Coach concept")

command("VimCoachPractice", function()
  coach.practice()
end, "Open the Vim Coach practice buffer")

command("VimCoachPracticeCheck", function()
  coach.practice_check()
end, "Check the Vim Coach practice buffer")

command("VimCoachPracticeReset", function()
  coach.practice_reset()
end, "Reset the Vim Coach practice buffer")

command("VimCoachResetData", function()
  coach.reset_data()
end, "Reset local Vim Coach data")

vim.api.nvim_create_user_command("VimCoachResetProfile", function(args)
  coach.reset_profile(args.bang)
end, {
  bang = true,
  desc = "Reset persisted Vim Coach lessons, goals, and progress",
})
