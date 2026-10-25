local M = {}

local state = {
  config = {},
  pending = {},
  lessons = {},
}

local function max_pending()
  return state.config.max_pending_episodes or 20
end

function M.setup(config)
  state.config = config or {}
  state.pending = {}
  state.lessons = {}
end

function M.enqueue(episode)
  if type(episode) ~= "table" or episode.id == nil then
    return false, "cannot queue an invalid episode"
  end
  for _, item in ipairs(state.pending) do
    if item.id == episode.id then
      return false, "episode is already queued"
    end
  end
  state.pending[#state.pending + 1] = episode
  while #state.pending > max_pending() do
    table.remove(state.pending, 1)
  end
  return true
end

function M.pending()
  return vim.deepcopy(state.pending)
end

function M.remove_ids(ids)
  local wanted = {}
  for _, id in ipairs(ids or {}) do
    wanted[id] = true
  end
  local remaining = {}
  for _, episode in ipairs(state.pending) do
    if not wanted[episode.id] then
      remaining[#remaining + 1] = episode
    end
  end
  state.pending = remaining
end

function M.add_lessons(suggestions, episodes)
  local by_id = {}
  for _, episode in ipairs(episodes or {}) do
    by_id[episode.id] = episode
  end
  for _, suggestion in ipairs(suggestions or {}) do
    local episode = by_id[suggestion.episodeId]
    for _, candidate in ipairs(suggestion.candidates or {}) do
      state.lessons[#state.lessons + 1] = {
        episode = episode and vim.deepcopy(episode) or nil,
        episodeId = suggestion.episodeId,
        proposal = vim.deepcopy(candidate),
      }
    end
  end
end

function M.clear()
  state.pending = {}
  state.lessons = {}
end

function M.status()
  return {
    pending = #state.pending,
    lessons = #state.lessons,
  }
end

return M
