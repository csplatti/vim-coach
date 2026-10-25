import unittest

from worker.candidates import generate_local_candidates, merge_candidates


class CandidateGenerationTests(unittest.TestCase):
    def test_navigation_generation_uses_cursor_delta_and_catalog(self):
        episode = {
            "id": 1,
            "kind": "navigation",
            "resolvedTokens": list("llllllll"),
            "before": {"cursor": {"row1Based": 1, "byteColumn0Based": 0}},
            "after": {"cursor": {"row1Based": 1, "byteColumn0Based": 8}},
        }
        candidates = generate_local_candidates(episode)
        compiled = [candidate["compiledTokens"] for candidate in candidates]
        self.assertIn(["8", "l"], compiled)
        self.assertIn(["$"], compiled)
        self.assertTrue(all(len(item) < 8 for item in compiled))

    def test_edit_generation_combines_semantic_motion_with_original_action(self):
        episode = {
            "id": 2,
            "kind": "edit",
            "resolvedTokens": list("llllx"),
            "before": {"lines": ["alpha beta"]},
            "after": {"lines": ["alph beta"]},
        }
        candidates = generate_local_candidates(episode)
        by_tokens = {tuple(candidate["compiledTokens"]): candidate for candidate in candidates}
        self.assertIn(("e", "x"), by_tokens)
        self.assertEqual(by_tokens[("e", "x")]["_featureKey"], "e")
        self.assertIn(("d", "i", "w"), by_tokens)

    def test_merge_keeps_provider_candidate_and_deduplicates_local_candidate(self):
        episode = {
            "id": 3,
            "kind": "navigation",
            "resolvedTokens": list("llll"),
            "before": {"cursor": {"row1Based": 1, "byteColumn0Based": 0}},
            "after": {"cursor": {"row1Based": 1, "byteColumn0Based": 4}},
        }
        provider = [{
            "episodeId": 3,
            "candidates": [{
                "tokens": [{"kind": "move", "key": "w"}],
                "compiledTokens": ["w"],
                "concept": "word motion",
                "explanation": "",
            }],
        }]
        merged = merge_candidates([episode], provider)[0]["candidates"]
        self.assertEqual(sum(item["compiledTokens"] == ["w"] for item in merged), 1)


if __name__ == "__main__":
    unittest.main()
