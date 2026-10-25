local M = {}

local state = {
  config = nil,
  card = nil,
  buffer = nil,
  window = nil,
  cooldown_until = 0,
  known_concepts = {},
}

local function now_ms()
  return vim.loop.hrtime() / 1000000
end

local function close_window()
  if state.window and vim.api.nvim_win_is_valid(state.window) then
    vim.api.nvim_win_close(state.window, true)
  end
  state.window = nil
  state.buffer = nil
end

local function token_text(tokens)
  local values = {}
  for _, token in ipairs(tokens or {}) do
    values[#values + 1] = tostring(token)
  end
  return table.concat(values, " ")
end

local function verified(proposal)
  local verification = proposal.verification or {}
  return proposal.verified == true or verification.accepted == true
end

local function comparison_scope(proposal)
  local verification = proposal.verification or {}
  local scope = {}
  if verification.textEqual == true then
    scope[#scope + 1] = "buffer text"
  end
  if verification.cursorEqual == true then
    scope[#scope + 1] = "cursor"
  end
  if verification.modeEqual == true then
    scope[#scope + 1] = "mode"
  end
  if verification.registersEqual == true then
    scope[#scope + 1] = "tracked registers"
  end
  if #scope == 0 then
    scope[#scope + 1] = "local replay"
  end
  return table.concat(scope, ", ")
end

local function render(proposal)
  local candidate = proposal.candidate or proposal
  local original = proposal.originalTokens or {}
  local replacement = candidate.compiledTokens or candidate.tokens or {}
  local original_count = proposal.originalLogicalKeys or #original
  local candidate_count = proposal.candidateLogicalKeys or #replacement
  local saved = proposal.savedLogicalKeys or (original_count - candidate_count)
  local explanation = candidate.explanation or proposal.explanation or "Use a shorter verified sequence."
  local concept = candidate.concept or proposal.concept or "general"

  return {
    " Vim Coach — verified suggestion ",
    "",
    " Original:  " .. token_text(original) .. "  (" .. original_count .. " logical keys)",
    " Try:       " .. token_text(replacement) .. "  (" .. candidate_count
      .. " logical keys; save " .. saved .. ")",
    "",
    " Why:       " .. explanation,
    " Verified:  " .. comparison_scope(proposal),
    " Concept:   " .. concept,
    "",
    " :VimCoachPractice   practice this edit",
    " :VimCoachDismiss    dismiss for the cooldown",
    " :VimCoachKnow       suppress this concept",
  }
end

function M.setup(config)
  state.config = config
end

function M.show(proposal)
  if type(proposal) ~= "table" or not verified(proposal) then
    return false, "proposal is not locally verified"
  end

  local candidate = proposal.candidate or proposal
  local original_count = proposal.originalLogicalKeys or #(proposal.originalTokens or {})
  local replacement = candidate.compiledTokens or candidate.tokens or {}
  local candidate_count = proposal.candidateLogicalKeys or #replacement
  if candidate_count >= original_count then
    return false, "candidate is not strictly shorter"
  end

  local concept = candidate.concept or proposal.concept or "general"
  if state.known_concepts[concept] then
    return false, "concept is suppressed"
  end
  if now_ms() < state.cooldown_until then
    return false, "suggestion cooldown is active"
  end

  close_window()
  state.card = proposal

  local lines = render(proposal)
  state.buffer = vim.api.nvim_create_buf(false, true)
  vim.bo[state.buffer].buftype = "nofile"
  vim.bo[state.buffer].bufhidden = "wipe"
  vim.bo[state.buffer].modifiable = true
  vim.b[state.buffer].vim_coach_ui = true
  vim.api.nvim_buf_set_lines(state.buffer, 0, -1, false, lines)
  vim.bo[state.buffer].modifiable = false

  local width = math.min(88, math.max(1, vim.o.columns - 6))
  local height = math.min(#lines, math.max(1, vim.o.lines - 6))
  state.window = vim.api.nvim_open_win(state.buffer, false, {
    relative = "editor",
    row = 2,
    col = 3,
    width = width,
    height = height,
    style = "minimal",
    border = "rounded",
  })
  vim.wo[state.window].wrap = false
  return true
end

function M.open()
  if not state.card then
    return false, "no verified lesson is available"
  end
  if state.window and vim.api.nvim_win_is_valid(state.window) then
    vim.api.nvim_set_current_win(state.window)
    return true
  end
  return M.show(state.card)
end

function M.dismiss(known)
  if not state.card then
    return false, "no lesson is open"
  end
  local candidate = state.card.candidate or state.card
  local concept = candidate.concept or state.card.concept or "general"
  if known then
    state.known_concepts[concept] = true
  else
    state.cooldown_until = now_ms() + (state.config and state.config.cooldown_ms or 60000)
  end
  state.card = nil
  close_window()
  return true
end

function M.reset()
  state.card = nil
  state.cooldown_until = 0
  state.known_concepts = {}
  close_window()
end

function M.status()
  local remaining = math.max(0, math.floor(state.cooldown_until - now_ms()))
  return {
    available = state.card ~= nil,
    open = state.window ~= nil and vim.api.nvim_win_is_valid(state.window),
    cooldownRemainingMs = remaining,
  }
end

return M
