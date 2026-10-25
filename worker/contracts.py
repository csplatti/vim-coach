"""Provider request/response contracts and trusted token compilation."""

from __future__ import annotations

from typing import Any

from replay.verify import validate_tokens


SCHEMA_VERSION = 1
BATCH_SCHEMA_VERSION = 2
MAX_CANDIDATES = 3
MAX_TOKENS = 128
MOVEMENT_KEYS = {"h", "j", "k", "l", "w", "b", "e", "W", "B", "E", "ge", "gg", "G", "0", "^", "$", "%"}


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
                    "key": {"enum": sorted(MOVEMENT_KEYS)},
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
        if key not in MOVEMENT_KEYS:
            raise ContractError("unsupported movement key")
        return list(key)
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
            raise ContractError(
                f"token {index} has unknown kind {kind!r}; expected count, move, or delete"
            )
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
            normalized_tokens.append(_normalize_token(token))
        compiled = compile_tokens(normalized_tokens)
        validated.append({
            "tokens": normalized_tokens,
            "compiledTokens": compiled,
            "concept": candidate["concept"][:64],
            "explanation": candidate["explanation"][:240],
        })
    return validated


def _normalize_token(token: Any) -> Any:
    """Normalize harmless provider naming variants before strict validation."""
    movements = MOVEMENT_KEYS
    deletes = {"x", "D", "dd", "dw", "diw", "daw"}
    if isinstance(token, str):
        if token in movements:
            return {"kind": "move", "key": token}
        if token in deletes:
            return {"kind": "delete", "command": token}
        if token.isdigit() and 1 <= int(token) <= 20:
            return {"kind": "count", "value": int(token)}
        return token
    if not isinstance(token, dict):
        return token
    kind = token.get("kind", token.get("type"))
    aliases = {
        "motion": "move",
        "movement": "move",
        "navigation": "move",
        "navigate": "move",
        "key": "move",
        "repeat": "count",
        "deletion": "delete",
        "remove": "delete",
    }
    kind = aliases.get(kind, kind)
    known_fields = {"kind", "type", "key", "command", "value", "count"}
    if not set(token).issubset(known_fields):
        return token

    def matching_value(*names: str) -> Any:
        values = [token[name] for name in names if name in token]
        if not values or any(value != values[0] for value in values[1:]):
            return None
        return values[0]

    if kind == "move":
        key = matching_value("key", "command", "value")
        if key is None:
            return token
        return {"kind": "move", "key": key}
    if kind == "count":
        value = matching_value("value", "count")
        if value is None:
            return token
        if isinstance(value, str) and value.isdigit():
            value = int(value)
        return {"kind": "count", "value": value}
    if kind == "delete":
        command = matching_value("command", "key", "value")
        if command is None:
            return token
        return {"kind": "delete", "command": command}
    return token


def validate_batch_response(value: Any, max_suggestions: int | None = None) -> list[dict[str, Any]]:
    if not isinstance(value, dict):
        raise ContractError("provider batch response must be an object")
    _require_exact_keys(value, {"schemaVersion", "suggestions"}, "batch response")
    if value["schemaVersion"] != BATCH_SCHEMA_VERSION:
        raise ContractError("unsupported provider batch schema version")
    suggestions = value["suggestions"]
    if not isinstance(suggestions, list):
        raise ContractError("suggestions must be an array")
    if max_suggestions is not None and len(suggestions) > max_suggestions:
        raise ContractError("suggestions cannot outnumber submitted episodes")

    validated: list[dict[str, Any]] = []
    for index, suggestion in enumerate(suggestions):
        if not isinstance(suggestion, dict):
            raise ContractError(f"suggestion {index} is not an object")
        if "episodeId" not in suggestion or "candidates" not in suggestion:
            raise ContractError(f"suggestion {index} requires episodeId and candidates")
        # Suggestion-level provider metadata is untrusted and unnecessary. Drop
        # it instead of failing the whole batch; candidate/token objects remain
        # strictly validated below.
        suggestion = {
            "episodeId": suggestion["episodeId"],
            "candidates": suggestion["candidates"],
        }
        if type(suggestion["episodeId"]) is not int:
            raise ContractError(f"suggestion {index} episodeId is invalid")
        candidates = validate_response({
            "schemaVersion": SCHEMA_VERSION,
            "candidates": suggestion["candidates"],
        })
        validated.append({"episodeId": suggestion["episodeId"], "candidates": candidates})
    return validated
