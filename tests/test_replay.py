import unittest
from unittest.mock import patch

from replay.verify import verify


class ReplayVerificationTests(unittest.TestCase):
    def test_live_register_restore_difference_does_not_reject_equivalent_replays(self):
        before = {
            "lines": ["one two"],
            "finalNewline": True,
            "cursor": {"row1Based": 1, "byteColumn0Based": 0},
        }
        expected = {
            "lines": ["one wo"],
            "finalNewline": True,
            "cursor": {"row1Based": 1, "byteColumn0Based": 4},
            "mode": "n",
            "trackedRegisters": {"\"": {"contents": ["live"], "type": "v"}},
        }
        replayed = {
            **expected,
            "trackedRegisters": {"\"": {"contents": ["replayed"], "type": "v"}},
        }
        with patch("replay.verify._run_child", side_effect=[replayed, replayed]):
            result = verify({
                "schemaVersion": 1,
                "before": before,
                "after": expected,
                "originalTokens": ["w", "x"],
                "candidateTokens": ["w", "x"],
            })
        self.assertTrue(result["originalReplayMatches"])
        self.assertTrue(result["candidateReplayMatches"])
        self.assertNotIn("trackedRegisters", result["originalMismatchFields"])


if __name__ == "__main__":
    unittest.main()
