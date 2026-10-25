local root = vim.fn.getcwd()
vim.opt.runtimepath:prepend(root)

local directory = vim.fn.tempname()
assert(vim.fn.mkdir(directory, "p") == 1, "could not create test directory")
local history_path = directory .. "/lessons.json"
local goals_path = directory .. "/goals.json"

local history = {
  schemaVersion = 1,
  lessons = {
    {
      lessonId = "word-motion",
      status = "new",
      helpTag = "w",
      concept = "Move by words",
      compiledTokens = { "w" },
    },
    {
      lessonId = "count-motion",
      status = "new",
      helpTag = "count",
      concept = "Counts",
      compiledTokens = { "3", "w" },
    },
    {
      lessonId = "dismissed-delete",
      status = "dismissed",
      helpTag = "x",
      concept = "Delete characters",
      compiledTokens = { "x" },
    },
  },
}
assert(vim.fn.writefile({ vim.fn.json_encode(history) }, history_path) == 0)

local progress = require("vim_coach.progress")
progress.setup({
  history_file = history_path,
  goals_file = goals_path,
  goal_target = 2,
})

local goals = progress.goals()
assert(#goals == 2, "only new, unique lessons should become goals")
assert(goals[1].featureId == "w")
assert(goals[2].featureId == "count")

local grammar = require("vim_coach.grammar")
local features = assert(grammar.feature_ids({ "3", "w", "d", "i", "w" }))
assert(vim.deep_equal(features, { "count", "w", "iw" }), "command features were parsed incorrectly")
assert(vim.deep_equal(assert(grammar.feature_ids({ "f", "x", "c", "i", '"', "a", string.char(27) })), { "f", 'ci"' }))

assert(#progress.record_tokens({ "3", "w" }) == 0)
goals = progress.goals()
assert(goals[1].progress == 1 and goals[2].progress == 1, "3w should reinforce count and word motion")
local completed = progress.record_tokens({ "w" })
assert(#completed == 1 and completed[1].featureId == "w", "word goal should complete at its target")

-- A successful one-key motion should reach progress tracking even though it is
-- intentionally below the threshold for creating a coaching episode.
vim.cmd("enew")
vim.api.nvim_buf_set_lines(0, 0, -1, false, { "one two" })
vim.api.nvim_win_set_cursor(0, { 1, 0 })
local observed = nil
local episodes = require("vim_coach.episodes")
episodes.setup({
  idle_ms = 10,
  max_lines = 100,
  max_buffer_bytes = 8192,
  max_episode_keys = 128,
  max_episode_ms = 10000,
  min_navigation_keys = 4,
}, nil, function(tokens)
  observed = tokens
end)
episodes.on_key("w", "w")
vim.cmd("normal! w")
assert(vim.wait(250, function()
  return observed ~= nil
end), "short successful motion was not observed")
assert(vim.deep_equal(observed, { "w" }))
assert(episodes.status().lastEpisodeId == nil, "short motion should not enter the coaching queue")
episodes.stop("test complete")

require("vim_coach.goals").open()
assert(vim.api.nvim_buf_get_name(0):match("vim%-coach://goals$"))
local goal_lines = vim.api.nvim_buf_get_lines(0, 0, -1, false)
assert(table.concat(goal_lines, "\n"):match("Move by words"), "goals view omitted active data")

require("vim_coach.stats").open()
assert(vim.api.nvim_buf_get_name(0):match("vim%-coach://stats$"))
local stat_lines = vim.api.nvim_buf_get_lines(0, 0, -1, false)
assert(table.concat(stat_lines, "\n"):match("1 feature learned"), "stats view omitted completion")

local persisted = vim.fn.json_decode(table.concat(vim.fn.readfile(goals_path), "\n"))
assert(persisted.schemaVersion == 1 and #persisted.goals == 2, "progress was not persisted")

-- Reconfiguring the demo target updates existing active goals instead of only
-- affecting lessons created after restart.
persisted.goals[2].target = 50
assert(vim.fn.writefile({ vim.fn.json_encode(persisted) }, goals_path) == 0)
progress.setup({ history_file = history_path, goals_file = goals_path, goal_target = 10 })
local retargeted = progress.goals()
assert(retargeted[2].target == 10, "configured target did not update an existing goal")

local reset_ok, reset_error = progress.reset_profile()
assert(reset_ok, reset_error or "profile reset failed")
local reset_goals = vim.fn.json_decode(table.concat(vim.fn.readfile(goals_path), "\n"))
local reset_history = vim.fn.json_decode(table.concat(vim.fn.readfile(history_path), "\n"))
assert(reset_goals.schemaVersion == 1 and #reset_goals.goals == 0, "profile reset kept goals")
assert(reset_history.schemaVersion == 1 and #reset_history.lessons == 0, "profile reset kept lessons")
assert(#progress.goals() == 0, "profile reset kept in-memory goals")
vim.fn.delete(directory, "rf")
