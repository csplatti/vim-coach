local grammar = require("vim_coach.grammar")

local M = {}

local SCHEMA_VERSION = 1
local state = {
  config = {},
  goals = {},
  path = nil,
}

local function now()
  return os.date("!%Y-%m-%dT%H:%M:%SZ")
end

local function default_state_path(filename)
  return vim.fn.expand("~/.local/state/vim-coach/" .. filename)
end

local function decode_file(path)
  if vim.fn.filereadable(path) ~= 1 then
    return nil
  end
  local ok, value = pcall(vim.fn.json_decode, table.concat(vim.fn.readfile(path), "\n"))
  if not ok or type(value) ~= "table" then
    return nil
  end
  return value
end

local function write_json(path, value, error_message)
  local directory = vim.fn.fnamemodify(path, ":h")
  vim.fn.mkdir(directory, "p")
  local temporary = path .. ".tmp"
  local encoded = vim.fn.json_encode(value)
  local ok = vim.fn.writefile({ encoded }, temporary)
  if ok ~= 0 then
    return false, error_message
  end
  local renamed = vim.loop.fs_rename(temporary, path)
  if not renamed then
    pcall(vim.fn.delete, temporary)
    return false, error_message
  end
  return true
end

local function save()
  return write_json(
    state.path,
    { schemaVersion = SCHEMA_VERSION, goals = state.goals },
    "could not write goal progress"
  )
end

local function load()
  local value = decode_file(state.path)
  if value and value.schemaVersion == SCHEMA_VERSION and type(value.goals) == "table" then
    state.goals = value.goals
  else
    state.goals = {}
  end
end

local function apply_configured_target()
  local target = tonumber(state.config.goal_target)
  if not target or target < 1 then
    return
  end
  local changed = false
  for _, goal in ipairs(state.goals) do
    if goal.status ~= "completed" and goal.target ~= target then
      goal.target = target
      changed = true
      if (goal.progress or 0) >= target then
        goal.progress = target
        goal.status = "completed"
        goal.completedAt = goal.completedAt or now()
      end
    end
  end
  if changed then
    save()
  end
end

local function history_path()
  return state.config.history_file
    or vim.env.VIM_COACH_HISTORY_FILE
    or default_state_path("lessons.json")
end

local function identity(lesson)
  if type(lesson.helpTag) == "string" and lesson.helpTag ~= "" then
    return lesson.helpTag
  end
  if type(lesson.concept) == "string" and lesson.concept ~= "" then
    return lesson.concept:lower()
  end
  return nil
end

function M.setup(config)
  state.config = config or {}
  state.path = state.config.goals_file
    or vim.env.VIM_COACH_GOALS_FILE
    or default_state_path("goals.json")
  load()
  apply_configured_target()
  M.sync_lessons()
end

function M.sync_lessons()
  local history = decode_file(history_path())
  if not history or history.schemaVersion ~= 1 or type(history.lessons) ~= "table" then
    return 0
  end
  local existing = {}
  for _, goal in ipairs(state.goals) do
    existing[goal.featureId] = true
  end
  local added = 0
  for _, lesson in ipairs(history.lessons) do
    local feature_id = identity(lesson)
    if lesson.status == "new" and feature_id and not existing[feature_id] then
      state.goals[#state.goals + 1] = {
        featureId = feature_id,
        title = lesson.concept or feature_id,
        binding = lesson.compiledTokens or {},
        target = state.config.goal_target or 50,
        progress = 0,
        status = "active",
        createdAt = now(),
      }
      existing[feature_id] = true
      added = added + 1
    end
  end
  if added > 0 then
    save()
  end
  return added
end

function M.record_tokens(tokens)
  local features, reason = grammar.feature_ids(tokens)
  if not features then
    return {}, reason
  end
  local uses = {}
  for _, feature_id in ipairs(features) do
    uses[feature_id] = (uses[feature_id] or 0) + 1
  end
  local changed = false
  local completed = {}
  for _, goal in ipairs(state.goals) do
    local count = uses[goal.featureId]
    if goal.status == "active" and count then
      goal.progress = math.min(goal.target, (goal.progress or 0) + count)
      goal.lastUsedAt = now()
      changed = true
      if goal.progress >= goal.target then
        goal.status = "completed"
        goal.completedAt = now()
        completed[#completed + 1] = vim.deepcopy(goal)
      end
    end
  end
  if changed then
    save()
  end
  return completed
end

function M.toggle(feature_id)
  for _, goal in ipairs(state.goals) do
    if goal.featureId == feature_id and goal.status ~= "completed" then
      goal.status = goal.status == "paused" and "active" or "paused"
      save()
      return true, goal.status
    end
  end
  return false, "goal not found or already completed"
end

function M.goals()
  return vim.deepcopy(state.goals)
end

function M.reset()
  state.goals = {}
  save()
end

function M.reset_profile()
  state.goals = {}
  local goals_ok, goals_error = save()
  if not goals_ok then
    return false, goals_error
  end
  local history_ok, history_error = write_json(
    history_path(),
    { schemaVersion = SCHEMA_VERSION, lessons = {} },
    "could not clear lesson history"
  )
  if not history_ok then
    return false, history_error
  end
  return true
end

return M
