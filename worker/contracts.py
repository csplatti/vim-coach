"""Provider request/response contracts and trusted token compilation."""

from __future__ import annotations

from typing import Any

from replay.verify import validate_tokens


SCHEMA_VERSION = 1
MAX_CANDIDATES = 3
MAX_TOKENS = 128


class ContractError(ValueError):
    """Raised when provider data does not match the local contract."""


def response_schema() -> dict[str, Any]:
    token_schema = {
        "anyOf": [
            {
                "type": "object",
                "properties": {
                    "kind": {"enum": ["count"]},
                    "value": {"type": "integer", "minimum": 1, "maximum": 20},
                },
                "required": ["kind", "value"],
                "additionalProperties": False,
            },
            {
                "type": "object",
                "properties": {
                    "kind": {"enum": ["move"]},
                    "key": {"enum": ["h", "l", "w", "b", "e", "0", "^", "$" ]},
                },
                "required": ["kind", "key"],
                "additionalProperties": False,
            },
            {
                "type": "object",
                "properties": {
                    "kind": {"enum": ["delete"]},
                    "command": {"enum": ["x", "D", "dd", "dw", "diw", "daw"]},
                },
                "required": ["kind", "command"],
                "additionalProperties": False,
            },
        ]
    }
    return {
        "type": "object",
        "properties": {
            "schemaVersion": {"enum": [SCHEMA_VERSION]},
            "candidates": {
                "type": "array",
                "minItems": 0,
                "maxItems": MAX_CANDIDATES,
                "items": {
                    "type": "object",
                    "properties": {
                        "tokens": {
                            "type": "array",
                            "minItems": 1,
                            "maxItems": MAX_TOKENS,
                            "items": token_schema,
                        },
                        "concept": {"type": "string", "maxLength": 64},
                        "explanation": {"type": "string", "maxLength": 240},
                    },
                    "required": ["tokens", "concept", "explanation"],
                    "additionalProperties": False,
                },
            },
        },
        "required": ["schemaVersion", "candidates"],
        "additionalProperties": False,
    }


def _require_exact_keys(value: dict[str, Any], required: set[str], label: str) -> None:
    if set(value) != required:
        raise ContractError(f"{label} must contain exactly: {sorted(required)}")


def _compile_token(token: dict[str, Any]) -> list[str]:
    kind = token.get("kind")
    if kind == "count":
        value = token.get("value")
        if type(value) is not int or not 1 <= value <= 20:
            raise ContractError("count value must be an integer from 1 to 20")
        return list(str(value))
    if kind == "move":
        key = token.get("key")
        if key not in {"h", "l", "w", "b", "e", "0", "^", "$"}:
            raise ContractError("unsupported movement key")
        return [key]
    if kind == "delete":
        command = token.get("command")
        if command not in {"x", "D", "dd", "dw", "diw", "daw"}:
            raise ContractError("unsupported delete command")
        return list(command)
    raise ContractError("unknown token kind")


def compile_tokens(tokens: Any) -> list[str]:
    if not isinstance(tokens, list) or not tokens or len(tokens) > MAX_TOKENS:
        raise ContractError("tokens must be a bounded non-empty array")
    compiled: list[str] = []
    for index, token in enumerate(tokens):
        if not isinstance(token, dict):
            raise ContractError(f"token {index} is not an object")
        kind = token.get("kind")
        required = {
            "count": {"kind", "value"},
            "move": {"kind", "key"},
            "delete": {"kind", "command"},
        }.get(kind)
        if required is None:
            raise ContractError(f"token {index} has an unknown kind")
        _require_exact_keys(token, required, f"token {index}")
        compiled.extend(_compile_token(token))
    if len(compiled) > MAX_TOKENS:
        raise ContractError("compiled token array is too large")
    valid, reason = validate_tokens(compiled)
    if not valid:
        raise ContractError(f"token sequence is not grammatically valid: {reason}")
    return compiled


def validate_response(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, dict):
        raise ContractError("provider response must be an object")
    _require_exact_keys(value, {"schemaVersion", "candidates"}, "response")
    if value["schemaVersion"] != SCHEMA_VERSION:
        raise ContractError("unsupported provider schema version")
    candidates = value["candidates"]
    if not isinstance(candidates, list) or len(candidates) > MAX_CANDIDATES:
        raise ContractError("candidates must contain at most three items")

    validated: list[dict[str, Any]] = []
    for index, candidate in enumerate(candidates):
        if not isinstance(candidate, dict):
            raise ContractError(f"candidate {index} is not an object")
        _require_exact_keys(candidate, {"tokens", "concept", "explanation"}, f"candidate {index}")
        if not isinstance(candidate["concept"], str):
            raise ContractError(f"candidate {index} concept is invalid")
        if not isinstance(candidate["explanation"], str):
            raise ContractError(f"candidate {index} explanation is invalid")
        normalized_tokens = []
        for token in candidate["tokens"]:
            if (
                isinstance(token, dict)
                and token.get("kind") == "move"
                and "key" not in token
                and set(token) == {"kind", "command"}
            ):
                token = {"kind": "move", "key": token["command"]}
            normalized_tokens.append(token)
        compiled = compile_tokens(normalized_tokens)
        validated.append({
            "tokens": normalized_tokens,
            "compiledTokens": compiled,
            "concept": candidate["concept"][:64],
            "explanation": candidate["explanation"][:240],
        })
    return validated
