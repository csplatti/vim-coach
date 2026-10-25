local M = {}

local ESC = string.char(27)
local simple_motions = {
  h = true, j = true, k = true, l = true,
  w = true, b = true, e = true,
  W = true, B = true, E = true,
  G = true, ["%"] = true, ["^"] = true, ["$"] = true,
  ["{"] = true, ["}"] = true, ["("] = true, [")"] = true,
  [";"] = true, [","] = true,
}
local find_commands = { f = true, F = true, t = true, T = true }
local text_objects = { w = true, ['"'] = true, ["("] = true, ["{"] = true }

local function is_digit(token)
  return type(token) == "string" and token:match("^%d$") ~= nil
end

local function is_literal(token)
  if type(token) ~= "string" or #token ~= 1 or token == ESC then
    return false
  end
  local byte = string.byte(token)
  return byte and byte >= 32 and byte <= 126
end

local function parse_count(tokens, index)
  if not tokens[index] or tokens[index] == "0" or not tokens[index]:match("^[1-9]$") then
    return index, nil
  end
  local value = 0
  while tokens[index] and is_digit(tokens[index]) do
    value = value * 10 + tonumber(tokens[index])
    index = index + 1
  end
  if value > 20 then
    return index, "count exceeds the supported limit of 20"
  end
  return index, nil
end

local function parse_insert_tail(tokens, index)
  while tokens[index] and tokens[index] ~= ESC do
    if not is_literal(tokens[index]) then
      return nil, "insert text contains an unsupported input"
    end
    index = index + 1
  end
  if tokens[index] ~= ESC then
    return nil, "insert or change command must end with Escape"
  end
  return index + 1, nil
end

local function parse_operator_target(tokens, index)
  local token = tokens[index]
  if token == "i" or token == "a" then
    if text_objects[tokens[index + 1]] then
      return index + 2, nil
    end
    return nil, "unsupported text object"
  end
  if token == "g" and tokens[index + 1] == "g" then
    return index + 2, nil
  end
  if token == "0" or token == "$" or token == "G" or token == "w" then
    return index + 1, nil
  end
  return nil, "unsupported operator target"
end

local function parse_visual(tokens, index)
  index = index + 1
  local moved = false
  while tokens[index] do
    local token = tokens[index]
    if (token == "d" or token == "x") and moved then
      return index + 1, nil, false
    end
    if token == "c" and moved then
      local tail_end, tail_error = parse_insert_tail(tokens, index + 1)
      if not tail_end then
        return nil, tail_error
      end
      return tail_end, nil, false
    end
    if (token == "i" or token == "a") and text_objects[tokens[index + 1]] then
      moved = true
      index = index + 2
    elseif token == "g" and (tokens[index + 1] == "g" or tokens[index + 1] == "e") then
      moved = true
      index = index + 2
    elseif find_commands[token] and is_literal(tokens[index + 1]) then
      moved = true
      index = index + 2
    else
      local motion_index, count_error = parse_count(tokens, index)
      if count_error then
        return nil, count_error
      end
      token = tokens[motion_index]
      if token == "0" or simple_motions[token] then
        moved = true
        index = motion_index + 1
      else
        return nil, "unsupported Visual-mode sequence"
      end
    end
  end
  return nil, "incomplete Visual-mode command"
end

local function parse_command(tokens, index)
  local next_index, count_error = parse_count(tokens, index)
  if count_error then
    return nil, count_error
  end
  index = next_index
  local token = tokens[index]
  if not token then
    return nil, "incomplete count or command"
  end

  if token == "0" or simple_motions[token] then
    return index + 1, nil, true
  end
  if token == "v" or token == "V" then
    return parse_visual(tokens, index)
  end
  if token == "g" then
    if tokens[index + 1] == "g" or tokens[index + 1] == "e" then
      return index + 2, nil, true
    end
    return nil, "unsupported g motion"
  end
  if find_commands[token] then
    if is_literal(tokens[index + 1]) then
      return index + 2, nil, true
    end
    return nil, "find motion requires one printable target"
  end
  if token == "x" or token == "D" or token == "dd" then
    return index + 1, nil, false
  end
  if token == "r" then
    if is_literal(tokens[index + 1]) then
      return index + 2, nil, false
    end
    return nil, "replace requires one printable character"
  end
  if token == "i" or token == "a" then
    return parse_insert_tail(tokens, index + 1)
  end
  if token == "C" then
    return parse_insert_tail(tokens, index + 1)
  end
  if token ~= "d" and token ~= "c" then
    return nil, "unsupported command sequence"
  end

  if token == "d" and tokens[index + 1] == "d" then
    return index + 2, nil, false
  end
  local target_end, target_error = parse_operator_target(tokens, index + 1)
  if not target_end then
    return nil, target_error
  end
  if token == "c" then
    local tail_end, tail_error = parse_insert_tail(tokens, target_end)
    if not tail_end then
      return nil, tail_error
    end
    return tail_end, nil, false
  end
  return target_end, nil, false
end

-- Normalize one on_key callback into one logical token. Printable ASCII is
-- accepted here because find/replace targets and inserted text are contextual;
-- the complete stateful grammar below decides where literals are legal.
function M.normalize(resolved, typed)
  if type(resolved) ~= "string" then
    return nil, nil, nil, "resolved input is not text"
  end
  local typed_value = typed
  if typed_value == nil or typed_value == "" then
    typed_value = resolved
  end
  if typed_value ~= resolved then
    return nil, typed_value, resolved, "remapped or ambiguous input"
  end
  if resolved ~= ESC and not is_literal(resolved) then
    return nil, typed_value, resolved, "unsupported input: " .. vim.inspect(resolved)
  end
  return resolved, typed_value, resolved, nil
end

function M.validate(tokens)
  if type(tokens) ~= "table" or #tokens == 0 then
    return false, "empty episode"
  end
  local index = 1
  while index <= #tokens do
    local next_index, reason = parse_command(tokens, index)
    if not next_index then
      return false, reason
    end
    index = next_index
  end
  return true
end

local function command_features(tokens, start_index, end_index)
  local features = {}
  local index = start_index
  if tokens[index] and tokens[index] ~= "0" and is_digit(tokens[index]) then
    features[#features + 1] = "count"
    while index < end_index and is_digit(tokens[index]) do
      index = index + 1
    end
  end

  local token = tokens[index]
  if token == "0" or simple_motions[token] then
    features[#features + 1] = token
  elseif token == "g" then
    features[#features + 1] = token .. (tokens[index + 1] or "")
  elseif find_commands[token] then
    features[#features + 1] = token
  elseif token == "x" or token == "D" or token == "r" or token == "C" or token == "dd" then
    features[#features + 1] = token
  elseif token == "d" then
    local target = tokens[index + 1]
    if target == "d" then
      features[#features + 1] = "dd"
    elseif target == "i" or target == "a" then
      features[#features + 1] = target .. (tokens[index + 2] or "")
    elseif target == "w" then
      features[#features + 1] = "d"
      features[#features + 1] = "w"
    elseif target == "g" and tokens[index + 2] == "g" then
      features[#features + 1] = "dgg"
    else
      features[#features + 1] = "d" .. (target or "")
    end
  elseif token == "c" then
    local target = tokens[index + 1]
    if target == "i" or target == "a" then
      features[#features + 1] = "c" .. target .. (tokens[index + 2] or "")
    else
      features[#features + 1] = "c" .. (target or "")
    end
  end
  return features
end

function M.feature_ids(tokens)
  if type(tokens) ~= "table" or #tokens == 0 then
    return nil, "empty episode"
  end
  local features = {}
  local index = 1
  while index <= #tokens do
    local next_index, reason = parse_command(tokens, index)
    if not next_index then
      return nil, reason
    end
    vim.list_extend(features, command_features(tokens, index, next_index))
    index = next_index
  end
  return features
end

function M.is_navigation_only(tokens)
  if type(tokens) ~= "table" or #tokens == 0 then
    return false
  end
  local index = 1
  while index <= #tokens do
    local next_index, reason, navigation = parse_command(tokens, index)
    if not next_index or reason or not navigation then
      return false
    end
    index = next_index
  end
  return true
end

return M
