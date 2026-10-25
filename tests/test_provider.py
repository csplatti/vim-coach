import unittest
import json
import os
from types import SimpleNamespace
from unittest.mock import patch

from worker.provider import (
    LLMClient,
    LLMConfig,
    build_batch_request,
    build_request,
    minimized_batch_payload,
    minimized_episode_payload,
)


class ProviderRequestTests(unittest.TestCase):
    @staticmethod
    def _response(content=None, reasoning_content=None):
        message = SimpleNamespace(content=content, reasoning_content=reasoning_content)
        return SimpleNamespace(choices=[SimpleNamespace(message=message)])

    def test_recovers_json_when_reasoning_model_omits_final_content(self):
        client = LLMClient(LLMConfig(api_key="test-key", cloud_enabled=True))
        response = self._response(
            reasoning_content='I should return the requested object. {"schemaVersion":2,"suggestions":[]}'
        )
        client._client = SimpleNamespace(
            chat=SimpleNamespace(completions=SimpleNamespace(create=lambda **_: response))
        )
        self.assertEqual(
            json.loads(client._completion_content({})),
            {"schemaVersion": 2, "suggestions": []},
        )

    def test_empty_final_content_is_a_successful_empty_batch(self):
        calls = []
        client = LLMClient(LLMConfig(api_key="test-key", cloud_enabled=True))
        client._client = SimpleNamespace(
            models=SimpleNamespace(list=lambda: SimpleNamespace(
                data=[SimpleNamespace(id="test-model")]
            )),
            chat=SimpleNamespace(completions=SimpleNamespace(
                create=lambda **_: calls.append(True) or self._response(reasoning_content="No useful proposal found.")
            )),
        )
        self.assertEqual(
            client.propose_batch([{"id": 1}]),
            {
                "schemaVersion": 2,
                "model": "test-model",
                "suggestions": [],
                "providerReturnedContent": False,
            },
        )
        self.assertEqual(len(calls), 2)

    def test_sdk_timeout_is_explicitly_disabled_by_default(self):
        captured = {}

        class FakeOpenAI:
            def __init__(self, **options):
                captured.update(options)

        with patch.dict("sys.modules", {"openai": type("FakeModule", (), {"OpenAI": FakeOpenAI})()}):
            LLMClient(LLMConfig(api_key="test-key"))._sdk()

        self.assertIn("timeout", captured)
        self.assertIsNone(captured["timeout"])

    def test_sdk_uses_configured_timeout_override(self):
        captured = {}

        class FakeOpenAI:
            def __init__(self, **options):
                captured.update(options)

        with patch.dict("sys.modules", {"openai": type("FakeModule", (), {"OpenAI": FakeOpenAI})()}):
            LLMClient(LLMConfig(api_key="test-key", timeout_seconds=45.5))._sdk()

        self.assertEqual(captured["timeout"], 45.5)

    def test_env_defaults_to_modal_with_provider_neutral_settings(self):
        with patch.dict(os.environ, {"MODAL_API_KEY": "modal-token"}, clear=True):
            config = LLMConfig.from_env(cloud_enabled=True)
        self.assertEqual(config.base_url, "https://inference.us-west.modal.direct/v1")
        self.assertIsNone(config.max_output_tokens)
        self.assertIsNone(config.max_retries)
        self.assertIsNone(config.timeout_seconds)

    def test_env_accepts_modal_endpoint_url(self):
        with patch.dict(os.environ, {
            "MODAL_API_KEY": "modal-token",
            "MODAL_BASE_URL": "https://example.modal.direct/v1",
        }, clear=True):
            config = LLMConfig.from_env(cloud_enabled=True)
        self.assertEqual(config.base_url, "https://example.modal.direct/v1")

    def test_payload_omits_local_only_state(self):
        episode = {
            "before": {
                "lines": ["one two"],
                "finalNewline": True,
                "cursor": {"row1Based": 1, "byteColumn0Based": 0},
                "trackedRegisters": {"\"": {"contents": ["secret"]}},
                "bufferPath": "/private/file.txt",
            },
            "after": {
                "lines": ["one"],
                "finalNewline": True,
                "cursor": {"row1Based": 1, "byteColumn0Based": 2},
                "trackedRegisters": {"\"": {"contents": ["secret"]}},
            },
            "resolvedTokens": ["d", "w"],
        }
        payload = minimized_episode_payload(episode)
        self.assertNotIn("trackedRegisters", json_keys(payload))
        self.assertNotIn("bufferPath", json_keys(payload))

    def test_navigation_episode_is_labeled_for_the_model(self):
        episode = {
            "kind": "navigation",
            "before": {"lines": ["one two"], "cursor": {"row1Based": 1, "byteColumn0Based": 0}},
            "after": {"lines": ["one two"], "cursor": {"row1Based": 1, "byteColumn0Based": 4}},
            "resolvedTokens": ["l", "l", "l", "l"],
        }
        payload = minimized_episode_payload(episode)
        self.assertEqual(payload["episodeKind"], "navigation")
        request = build_batch_request(LLMConfig(api_key="test-key"), [{"id": 1, **episode}])
        self.assertIn("For navigation episodes", request["messages"][0]["content"])
        self.assertIn("Prioritize semantic motions", request["messages"][0]["content"])

    def test_request_uses_json_output(self):
        config = LLMConfig(api_key="test-key")
        request = build_request(config, {
            "before": {"lines": ["one"], "cursor": {}},
            "after": {"lines": ["on"], "cursor": {}},
            "resolvedTokens": ["x"],
        })
        self.assertEqual(request["response_format"], {"type": "json_object"})
        self.assertIn("teach one reusable Vim feature", request["messages"][0]["content"])
        self.assertIn("Do not discuss mistakes", request["messages"][0]["content"])
        self.assertNotIn("max_tokens", request)
        self.assertNotIn("test-key", json.dumps(request))

    def test_max_tokens_is_sent_only_when_configured(self):
        with patch.dict(os.environ, {
            "MODAL_API_KEY": "modal-token",
            "LLM_MAX_OUTPUT_TOKENS": "2048",
        }, clear=True):
            config = LLMConfig.from_env(cloud_enabled=True)
        request = build_request(config, {
            "before": {"lines": ["one"], "cursor": {}},
            "after": {"lines": ["on"], "cursor": {}},
            "resolvedTokens": ["x"],
        })
        self.assertEqual(request["max_tokens"], 2048)

    def test_retry_and_timeout_are_loaded_only_when_configured(self):
        with patch.dict(os.environ, {
            "MODAL_API_KEY": "modal-token",
            "LLM_MAX_RETRIES": "2",
            "LLM_TIMEOUT_SECONDS": "45.5",
        }, clear=True):
            config = LLMConfig.from_env(cloud_enabled=True)
        self.assertEqual(config.max_retries, 2)
        self.assertEqual(config.timeout_seconds, 45.5)

    def test_batch_payload_keeps_episode_boundaries(self):
        episodes = [
            {"id": 7, "before": {"lines": ["one"]}, "after": {"lines": ["on"]}, "resolvedTokens": ["x"]},
            {"id": 8, "before": {"lines": ["two"]}, "after": {"lines": ["tw"]}, "resolvedTokens": ["x"]},
        ]
        payload = minimized_batch_payload(episodes)
        self.assertEqual([item["episodeId"] for item in payload], [7, 8])
        self.assertEqual(payload[0]["episode"]["originalTokens"], ["x"])
        request = build_batch_request(LLMConfig(api_key="test-key"), episodes)
        self.assertEqual(request["model"], "auto")
        self.assertEqual(request["response_format"], {"type": "json_object"})
        self.assertNotIn("max_tokens", request)
        self.assertEqual(len(request["messages"]), 2)
        self.assertNotIn("test-key", json.dumps(request))


def json_keys(value):
    if isinstance(value, dict):
        result = set(value)
        for child in value.values():
            result |= json_keys(child)
        return result
    if isinstance(value, list):
        result = set()
        for child in value:
            result |= json_keys(child)
        return result
    return set()


if __name__ == "__main__":
    unittest.main()
