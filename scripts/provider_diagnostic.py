#!/usr/bin/env python3
"""Diagnose a Modal/OpenAI-compatible inference endpoint."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


DEFAULT_BASE_URL = "https://inference.us-west.modal.direct/v1"
DEFAULT_MODEL = "auto"
RESPONSE_HEADERS = ("x-request-id", "x-trace-id", "cf-ray", "content-type")


def load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        name = name.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        os.environ.setdefault(name, value)


def request_json(method: str, url: str, api_key: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
    data = json.dumps(body, separators=(",", ":")).encode("utf-8") if body is not None else None
    request = Request(
        url,
        data=data,
        method=method,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
    )
    started = time.monotonic()
    try:
        with urlopen(request, timeout=20) as response:
            status = response.status
            headers = dict(response.headers.items())
            raw = response.read(64 * 1024)
    except HTTPError as error:
        status = error.code
        headers = dict(error.headers.items())
        raw = error.read(64 * 1024)
    except (URLError, TimeoutError) as error:
        return {
            "status": None,
            "elapsedMs": round((time.monotonic() - started) * 1000, 1),
            "headers": {},
            "body": {"transportError": str(error)},
        }

    try:
        body_value: Any = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        body_value = raw.decode("utf-8", errors="replace")
    return {
        "status": status,
        "elapsedMs": round((time.monotonic() - started) * 1000, 1),
        "headers": {name: headers[name] for name in RESPONSE_HEADERS if name in headers},
        "body": body_value,
    }


def diagnosis(status: int | None, body: Any) -> str:
    if status is None:
        return "Network or DNS failure; retry from a networked terminal."
    if status == 200:
        return "Success."
    if status == 401:
        return "The API key is missing or invalid."
    if status == 403:
        code = body.get("error", {}).get("code") if isinstance(body, dict) else None
        if code == "NOT_ENOUGH_BALANCE":
            return "The provider reports insufficient balance or access."
        return "The provider refused the request: check token permissions or model access."
    if status == 404:
        return "The endpoint or model was not found; verify the exact model ID."
    if status == 400:
        return "The request body or response-format schema was rejected."
    if status == 429:
        return "The account or endpoint is rate/token limited."
    return f"Unexpected HTTP {status}; inspect the provider body and request IDs."


def print_result(label: str, result: dict[str, Any]) -> None:
    print(f"\n== {label} ==")
    print(f"HTTP: {result['status']}  latency: {result['elapsedMs']} ms")
    if result["headers"]:
        print("headers:", json.dumps(result["headers"], sort_keys=True))
    print("body:")
    print(json.dumps(result["body"], indent=2, sort_keys=True))
    print("diagnosis:", diagnosis(result["status"], result["body"]))


def chat_body(model: str, mode: str, max_tokens: int | None = None) -> dict[str, Any]:
    body: dict[str, Any] = {
        "model": model,
        "messages": [{"role": "user", "content": "Reply with one short sentence: API diagnostic passed."}],
        "stream": False,
        "reasoning_effort": "low",
    }
    if max_tokens is not None:
        body["max_tokens"] = max_tokens
    if mode == "json_object":
        body["messages"] = [{"role": "user", "content": "Return exactly JSON: {\"ok\":true}."}]
        body["response_format"] = {"type": "json_object"}
    elif mode == "json_schema":
        body["messages"] = [{"role": "user", "content": "Return an object with ok set to true."}]
        body["response_format"] = {
            "type": "json_schema",
            "json_schema": {
                "name": "diagnostic_result",
                "strict": True,
                "schema": {
                    "type": "object",
                    "properties": {"ok": {"type": "boolean"}},
                    "required": ["ok"],
                    "additionalProperties": False,
                },
            },
        }
    return body


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, default=Path(".env"))
    parser.add_argument("--mode", choices=["models", "basic", "json_object", "json_schema", "all"], default="models")
    args = parser.parse_args()

    load_env_file(args.env_file)
    api_key = os.environ.get("MODAL_API_KEY", "")
    model = DEFAULT_MODEL
    max_tokens = None
    if os.environ.get("LLM_MAX_OUTPUT_TOKENS"):
        max_tokens = int(os.environ["LLM_MAX_OUTPUT_TOKENS"])
    if not api_key:
        parser.error("MODAL_API_KEY is missing; use --env-file or export it")

    base_url = os.environ.get("MODAL_BASE_URL", DEFAULT_BASE_URL).rstrip("/")
    print("Modal/provider diagnostic")
    print("base URL:", base_url)
    print("API key:", "loaded (value hidden)")
    print("model: auto-discovered from /v1/models")

    modes = ["models"] if args.mode == "models" else (["basic", "json_object", "json_schema"] if args.mode == "all" else [args.mode])
    if args.mode != "models":
        models_result = request_json("GET", base_url + "/models", api_key)
        print_result("models", models_result)
        if models_result["status"] != 200:
            return 1
        if isinstance(models_result["body"], dict):
            data = models_result["body"].get("data", [])
            model_ids = [item.get("id") for item in data if isinstance(item, dict) and isinstance(item.get("id"), str)]
            if model_ids:
                model = model_ids[0]
                print("using discovered endpoint:", model)
    for mode in modes:
        if mode == "models":
            result = request_json("GET", base_url + "/models", api_key)
        else:
            result = request_json("POST", base_url + "/chat/completions", api_key, chat_body(model, mode, max_tokens))
        print_result(mode, result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
