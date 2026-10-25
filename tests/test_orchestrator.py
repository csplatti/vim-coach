import json
import os
from pathlib import Path
import unittest
from unittest.mock import patch

from replay.verify import _nvim_executable
from worker.orchestrator import augment_local_candidates, verify_batch_candidates, verify_candidates


class OrchestratorTests(unittest.TestCase):
    def test_augments_navigation_with_semantic_single_motions(self):
        result = augment_local_candidates([{
            "id": 9,
            "kind": "navigation",
            "resolvedTokens": list("llllllll"),
            "before": {"cursor": {"row1Based": 1, "byteColumn0Based": 0}},
            "after": {"cursor": {"row1Based": 1, "byteColumn0Based": 7}},
        }], [])
        candidates = result[0]["candidates"]
        compiled = [candidate["compiledTokens"] for candidate in candidates]
        self.assertIn(["w"], compiled)
        self.assertIn(["g", "e"], compiled)
        self.assertIn(["%"], compiled)
        self.assertIn(["7", "l"], compiled)

    def test_augments_repeated_motion_with_a_count(self):
        result = augment_local_candidates([{
            "id": 10,
            "kind": "edit",
            "resolvedTokens": ["0", "w", "w", "w", "x"],
        }], [])
        candidate = next(
            item for item in result[0]["candidates"]
            if item["compiledTokens"] == ["0", "3", "w", "x"]
        )
        self.assertEqual(candidate["compiledTokens"], ["0", "3", "w", "x"])
        self.assertEqual(candidate["tokens"], [
            {"kind": "move", "key": "0"},
            {"kind": "count", "value": 3},
            {"kind": "move", "key": "w"},
            {"kind": "delete", "command": "x"},
        ])

    def test_specialized_local_motion_ranks_over_generic_equivalents(self):
        candidates = [
            {
                "tokens": [{"kind": "move", "key": key}],
                "compiledTokens": list(key),
                "concept": key,
                "explanation": "",
                "_rankingPriority": priority,
            }
            for key, priority in (("w", 50), ("e", 50), ("$", 80))
        ]
        replay_result = {
            "accepted": True,
            "originalReplayMatches": True,
            "candidateReplayMatches": True,
            "originalLogicalKeys": 5,
            "candidateLogicalKeys": 1,
            "savedLogicalKeys": 4,
            "originalReplayLatencyMs": 1,
            "candidateReplayLatencyMs": 1,
        }
        with patch("worker.orchestrator.verify_many", return_value=[replay_result] * 3):
            result = verify_candidates({
                "id": 1,
                "before": {},
                "after": {},
                "resolvedTokens": list("lllll"),
            }, candidates)
        self.assertEqual(result[0]["compiledTokens"], ["$"])

    def test_unseen_feature_ranks_before_previous_exposure(self):
        candidates = [
            {
                "tokens": [{"kind": "move", "key": key}],
                "compiledTokens": [key],
                "concept": key,
                "explanation": "",
            }
            for key in ("w", "e")
        ]
        replay_result = {
            "accepted": True,
            "originalReplayMatches": True,
            "candidateReplayMatches": True,
            "originalLogicalKeys": 5,
            "candidateLogicalKeys": 1,
            "savedLogicalKeys": 4,
            "originalReplayLatencyMs": 1,
            "candidateReplayLatencyMs": 1,
        }
        with patch("worker.orchestrator.verify_many", return_value=[replay_result] * 2):
            result = verify_candidates({
                "before": {},
                "after": {},
                "resolvedTokens": list("lllll"),
            }, candidates, lesson_profile={"w": {"exposures": 2}})
        self.assertEqual(result[0]["compiledTokens"], ["e"])
        self.assertNotIn(["w"], [item["compiledTokens"] for item in result])

    def test_neovim_server_socket_is_not_used_as_the_replay_executable(self):
        with patch.dict(os.environ, {"NVIM": "/tmp/nvim.socket"}, clear=True):
            self.assertEqual(_nvim_executable(), "nvim")

        with patch.dict(os.environ, {"VIM_COACH_NVIM": "/opt/nvim/bin/nvim"}, clear=True):
            self.assertEqual(_nvim_executable(), "/opt/nvim/bin/nvim")

    def test_only_replay_verified_candidates_are_returned(self):
        fixture = json.loads(Path("tests/fixtures/replay-basic.json").read_text())
        candidates = [
            {
                "tokens": [],
                "compiledTokens": ["w", "x"],
                "concept": "wrong",
                "explanation": "wrong target",
            },
            {
                "tokens": [],
                "compiledTokens": fixture["candidateTokens"],
                "concept": "counted-movement",
                "explanation": "Use a count.",
            },
        ]
        result = verify_candidates({
            "before": fixture["before"],
            "after": fixture["after"],
            "resolvedTokens": fixture["originalTokens"],
        }, candidates)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["savedLogicalKeys"], 1)
        self.assertTrue(result[0]["verified"])

    def test_batch_verification_preserves_episode_ids(self):
        fixture = json.loads(Path("tests/fixtures/replay-basic.json").read_text())
        episode = {
            "id": 12,
            "before": fixture["before"],
            "after": fixture["after"],
            "resolvedTokens": fixture["originalTokens"],
        }
        result = verify_batch_candidates([episode], [{
            "episodeId": 12,
            "candidates": [{
                "tokens": [],
                "compiledTokens": fixture["candidateTokens"],
                "concept": "counted-movement",
                "explanation": "Use a count.",
            }],
        }])
        self.assertEqual(result[0]["episodeId"], 12)
        self.assertEqual(len(result[0]["candidates"]), 1)

    def test_restores_omitted_leading_positioning_command_when_replay_proves_it(self):
        fixture = json.loads(Path("tests/fixtures/replay-basic.json").read_text())
        before = {**fixture["before"], "cursor": {"row1Based": 1, "byteColumn0Based": 17}}
        episode = {
            "id": 13,
            "before": before,
            "after": fixture["after"],
            "resolvedTokens": ["0", *fixture["originalTokens"]],
        }
        result = verify_candidates(episode, [{
            "tokens": [
                {"kind": "count", "value": 3},
                {"kind": "move", "key": "w"},
                {"kind": "delete", "command": "x"},
            ],
            "compiledTokens": fixture["candidateTokens"],
            "concept": "counted-movement",
            "explanation": "Use a count.",
        }])
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["compiledTokens"], ["0", "3", "w", "x"])
        self.assertEqual(result[0]["savedLogicalKeys"], 1)


if __name__ == "__main__":
    unittest.main()
