local M = {}

local motions = {
  ["h"] = true,
  ["j"] = true,
  ["k"] = true,
  ["l"] = true,
  ["w"] = true,
  ["b"] = true,
  ["e"] = true,
  ["W"] = true,
  ["B"] = true,
  ["E"] = true,
  ["G"] = true,
  ["%"] = true,
  ["^"] = true,
  ["$"] = true,
}

local supported = {
  ["h"] = true,
  ["j"] = true,
  ["k"] = true,
  ["l"] = true,
  ["w"] = true,
  ["b"] = true,
  ["e"] = true,
  ["W"] = true,
  ["B"] = true,
  ["E"] = true,
  ["G"] = true,
  ["g"] = true,
  ["%"] = true,
  ["0"] = true,
  ["^"] = true,
  ["$"] = true,
  ["x"] = true,
  ["D"] = true,
  ["d"] = true,
  ["i"] = true,
  ["a"] = true,
}

for digit = 1, 9 do
  supported[tostring(digit)] = true
end

local function is_digit(token)
  return type(token) == "string" and token:match("^%d$") ~= nil
end

local function parse_count(tokens, index)
  if not tokens[index] or tokens[index] == "0" then
    return index, nil
  end

  if not tokens[index]:match("^[1-9]$") then
    return index, nil
  end

  local start = index
  local value = 0
  while tokens[index] and is_digit(tokens[index]) do
    value = value * 10 + tonumber(tokens[index])
    index = index + 1
  end

  if value > 20 then
    return index, "count exceeds the supported limit of 20"
  end

  return index, nil, start
end

-- Normalize one on_key callback into one logical token. Typed and resolved
-- values are kept separate by the recorder; remapped or ambiguous input is
-- rejected instead of being guessed.
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

  if #resolved ~= 1 or not supported[resolved] then
    return nil, typed_value, resolved, "unsupported input: " .. vim.inspect(resolved)
  end

  return resolved, typed_value, resolved, nil
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

  if token == "0" and index == next_index then
    return index + 1, nil
  end

  if token == "g" then
    if tokens[index + 1] == "g" or tokens[index + 1] == "e" then
      return index + 2, nil
    end
    return nil, "unsupported g motion"
  end

  if motions[token] or token == "x" or token == "D" then
    return index + 1, nil
  end

  if token ~= "d" then
    return nil, "unsupported command sequence"
  end

  local operator = tokens[index + 1]
  if not operator then
    return nil, "incomplete delete operator"
  end

  if operator == "d" or operator == "w" then
    return index + 2, nil
  end

  if operator == "i" or operator == "a" then
    if tokens[index + 2] == "w" then
      return index + 3, nil
    end
    return nil, "incomplete text-object delete"
  end

  return nil, "unsupported delete command"
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

function M.is_navigation_only(tokens)
  local valid = M.validate(tokens)
  if not valid then
    return false
  end
  for _, token in ipairs(tokens) do
    if not is_digit(token) and token ~= "0" and token ~= "g" and not motions[token] then
      return false
    end
  end
  return true
end

return M
