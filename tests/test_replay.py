import unittest
from unittest.mock import patch

from replay.verify import validate_tokens, verify, verify_many


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

    def test_many_candidates_replay_original_once(self):
        state = {
            "lines": ["alpha"],
            "finalNewline": True,
            "cursor": {"row1Based": 1, "byteColumn0Based": 0},
            "mode": "n",
            "trackedRegisters": {},
        }
        with patch("replay.verify._run_child", return_value=state) as run_child:
            results = verify_many({
                "schemaVersion": 1,
                "before": state,
                "after": state,
                "originalTokens": ["h", "l", "h", "l"],
                "candidateTokenSets": [["w"], ["e"]],
            })
        self.assertEqual(len(results), 2)
        self.assertEqual(run_child.call_count, 3)

    def test_editing_outcome_policy_reports_but_allows_register_difference(self):
        base = {
            "lines": ["alpha"],
            "finalNewline": True,
            "cursor": {"row1Based": 1, "byteColumn0Based": 0},
            "mode": "n",
        }
        original = {**base, "trackedRegisters": {"\"": {"contents": ["a"], "type": "v"}}}
        candidate = {**base, "trackedRegisters": {"\"": {"contents": ["alpha"], "type": "v"}}}
        with patch("replay.verify._run_child", side_effect=[original, candidate]):
            result = verify_many({
                "schemaVersion": 1,
                "before": base,
                "after": base,
                "originalTokens": ["x", "x", "x", "x"],
                "candidateTokenSets": [["D"]],
                "requireRegisterEquality": False,
            })[0]
        self.assertTrue(result["accepted"])
        self.assertFalse(result["registersEqual"])
        self.assertEqual(result["comparisonPolicy"], "editing-outcome")

    def test_accepts_bounded_visual_edit_sequences(self):
        self.assertEqual(validate_tokens(list("vllld")), (True, ""))
        self.assertEqual(validate_tokens(list("Vjd")), (True, ""))
        self.assertEqual(validate_tokens(["v", "i", '"', "c", "x", "\x1b"]), (True, ""))
        valid, reason = validate_tokens(list("vlll"))
        self.assertFalse(valid)
        self.assertIn("incomplete Visual-mode", reason)


if __name__ == "__main__":
    unittest.main()
