import unittest
import json

from worker.bitdeer import BitdeerConfig, build_request, minimized_episode_payload


class BitdeerRequestTests(unittest.TestCase):
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

    def test_request_uses_structured_output(self):
        config = BitdeerConfig(api_key="test-key", model="test-model")
        request = build_request(config, {
            "before": {"lines": ["one"], "cursor": {}},
            "after": {"lines": ["on"], "cursor": {}},
            "resolvedTokens": ["x"],
        })
        self.assertNotIn("response_format", request)
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
