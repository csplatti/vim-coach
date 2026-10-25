local requests = {}
local worker_active = false
local worker_callback = nil
local episode_callback = nil

package.loaded["vim_coach.recorder"] = {
  setup = function(_, on_episode)
    episode_callback = on_episode
  end,
  stop = function() end,
  cancel = function() end,
  pause = function() end,
  resume = function() end,
  reset = function() end,
  status = function()
    return {
      healthy = true,
      started = true,
      episode = { lastSkipReason = "none" },
    }
  end,
  last_episode = function() return nil end,
}

package.loaded["vim_coach.worker"] = {
  setup = function(_, on_result)
    worker_callback = on_result
  end,
  request_batch = function(episodes)
    worker_active = true
    requests[#requests + 1] = vim.deepcopy(episodes)
    return true
  end,
  status = function() return { active = worker_active } end,
  cancel = function() worker_active = false end,
}

package.loaded["vim_coach.ui"] = {
  setup = function() end,
  status = function() return { available = false } end,
  reset = function() end,
}
package.loaded["vim_coach.practice"] = {
  setup = function() end,
  status = function() return { open = false } end,
  close = function() end,
}
package.loaded["vim_coach.progress"] = {
  setup = function() end,
  record_tokens = function() return {} end,
}
package.loaded["vim_coach.goals"] = { open = function() end }
package.loaded["vim_coach.stats"] = { open = function() end }
package.loaded["vim_coach.init"] = nil

local coach = require("vim_coach")
coach.setup({ enabled = true, cloud_enabled = true })
assert(type(episode_callback) == "function", "recorder callback was not installed")
assert(type(worker_callback) == "function", "worker callback was not installed")

local function episode(id)
  return { id = id, originalLogicalKeyCount = 4 }
end

episode_callback(episode(1))
vim.wait(200, function() return #requests == 1 end)
assert(#requests == 1 and #requests[1] == 1, "first episode was not sent immediately")

episode_callback(episode(2))
episode_callback(episode(3))
vim.wait(20)
assert(#requests == 1, "overlapping episodes started a concurrent request")

worker_active = false
worker_callback({ suggestions = {}, providerReturnedContent = true, providerCandidateCount = 0 }, nil)
vim.wait(200, function() return #requests == 2 end)
assert(#requests == 2 and #requests[2] == 2, "queued overlap was not sent as one follow-up batch")
assert(requests[2][1].id == 2 and requests[2][2].id == 3, "follow-up batch order changed")

worker_active = false
worker_callback({ suggestions = {}, providerReturnedContent = true, providerCandidateCount = 0 }, nil)
vim.wait(20)

episode_callback(episode(4))
vim.wait(200, function() return #requests == 3 end)
episode_callback(episode(5))
worker_active = false
worker_callback(nil, "test failure")
vim.wait(50)
assert(#requests == 3, "failed batch retried in a loop")

episode_callback(episode(6))
vim.wait(200, function() return #requests == 4 end)
assert(#requests[4] == 3, "failed and newly queued episodes were not preserved for retry")
assert(
  requests[4][1].id == 4 and requests[4][2].id == 5 and requests[4][3].id == 6,
  "retry batch did not preserve episode order"
)
