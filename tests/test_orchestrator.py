import json
from pathlib import Path
import unittest

from worker.orchestrator import verify_candidates


class OrchestratorTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
