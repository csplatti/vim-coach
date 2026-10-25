import unittest

from worker.contracts import ContractError, compile_tokens, validate_batch_response, validate_response


class ContractTests(unittest.TestCase):
    def test_compiles_safe_tokens(self):
        self.assertEqual(
            compile_tokens([
                {"kind": "count", "value": 3},
                {"kind": "move", "key": "w"},
                {"kind": "delete", "command": "x"},
            ]),
            ["3", "w", "x"],
        )

    def test_compiles_advanced_motion_tokens(self):
        self.assertEqual(
            compile_tokens([
                {"kind": "move", "key": "gg"},
                {"kind": "move", "key": "ge"},
                {"kind": "move", "key": "%"},
            ]),
            ["g", "g", "g", "e", "%"],
        )

    def test_compiles_find_text_object_change_and_replace_tokens(self):
        self.assertEqual(
            compile_tokens([
                {"kind": "find", "command": "f", "target": ")"},
                {"kind": "delete", "command": 'di"'},
                {"kind": "change", "command": "ciw", "text": "name"},
                {"kind": "replace", "target": "_"},
            ]),
            ["f", ")", "d", "i", '"', "c", "i", "w", "n", "a", "m", "e", "\x1b", "r", "_"],
        )

    def test_compiles_structural_and_operator_motions(self):
        self.assertEqual(
            compile_tokens([
                {"kind": "move", "key": "}"},
                {"kind": "delete", "command": "dgg"},
            ]),
            ["}", "d", "g", "g"],
        )

    def test_rejects_control_characters_in_literal_fields(self):
        with self.assertRaises(ContractError):
            compile_tokens([{"kind": "find", "command": "f", "target": "\n"}])
        with self.assertRaises(ContractError):
            compile_tokens([{"kind": "change", "command": "ciw", "text": "bad\ntext"}])

    def test_rejects_unknown_fields(self):
        with self.assertRaises(ContractError):
            validate_response({
                "schemaVersion": 1,
                "candidates": [{
                    "tokens": [{"kind": "move", "key": "w", "run": "shell"}],
                    "concept": "motion",
                    "explanation": "safe",
                }],
            })

    def test_rejects_visual_mode_token(self):
        with self.assertRaises(ContractError):
            compile_tokens([
                {"kind": "move", "key": "v"},
            ])

    def test_validates_batch_response(self):
        result = validate_batch_response({
            "schemaVersion": 2,
            "suggestions": [{
                "episodeId": 4,
                "candidates": [{
                    "tokens": [{"kind": "move", "key": "w"}],
                    "concept": "word-motion",
                    "explanation": "Move by word.",
                }],
            }],
        })
        self.assertEqual(result[0]["episodeId"], 4)
        self.assertEqual(result[0]["candidates"][0]["compiledTokens"], ["w"])

    def test_batch_size_is_bounded_by_submitted_episode_count(self):
        value = {
            "schemaVersion": 2,
            "suggestions": [
                {"episodeId": index, "candidates": []}
                for index in range(21)
            ],
        }
        self.assertEqual(len(validate_batch_response(value, max_suggestions=21)), 21)
        with self.assertRaises(ContractError):
            validate_batch_response(value, max_suggestions=20)

    def test_ignores_null_episode_metadata_in_batch_suggestion(self):
        result = validate_batch_response({
            "schemaVersion": 2,
            "suggestions": [{
                "episodeId": 4,
                "episode": None,
                "candidates": [{
                    "tokens": [{"kind": "move", "key": "w"}],
                    "concept": "word-motion",
                    "explanation": "Move by word.",
                }],
            }],
        })
        self.assertEqual(result[0]["episodeId"], 4)

    def test_discards_untrusted_suggestion_metadata(self):
        result = validate_batch_response({
            "schemaVersion": 2,
            "suggestions": [{
                "episodeId": 4,
                "episode": {"unexpected": "source echo"},
                "providerNote": "unused",
                "candidates": [],
            }],
        })
        self.assertEqual(result, [{"episodeId": 4, "candidates": []}])

    def test_ignores_empty_episode_id_note(self):
        result = validate_batch_response({
            "schemaVersion": 2,
            "suggestions": [{
                "episodeId": 4,
                "episodeIdNote": "",
                "candidates": [{
                    "tokens": [{"kind": "delete", "value": "x"}],
                    "concept": "Delete characters",
                    "explanation": "Delete the character under the cursor.",
                }],
            }],
        })
        self.assertEqual(result[0]["candidates"][0]["compiledTokens"], ["x"])

    def test_requires_suggestion_identity_and_candidates(self):
        with self.assertRaises(ContractError):
            validate_batch_response({"schemaVersion": 2, "suggestions": [{"episodeId": 4}]})

    def test_normalizes_safe_provider_token_aliases(self):
        result = validate_response({
            "schemaVersion": 1,
            "candidates": [{
                "tokens": [{"kind": "motion", "value": "w"}, "x"],
                "concept": "word-motion",
                "explanation": "Move by word, then delete.",
            }],
        })
        self.assertEqual(result[0]["compiledTokens"], ["w", "x"])

    def test_normalizes_redundant_matching_provider_fields(self):
        result = validate_response({
            "schemaVersion": 1,
            "candidates": [{
                "tokens": [
                    {"kind": "move", "key": "w", "value": "w"},
                    {"kind": "delete", "command": "x", "key": "x"},
                ],
                "concept": "redundant-fields",
                "explanation": "Equivalent aliases are harmless.",
            }],
        })
        self.assertEqual(result[0]["compiledTokens"], ["w", "x"])

    def test_normalizes_numeric_string_count(self):
        result = validate_response({
            "schemaVersion": 1,
            "candidates": [{
                "tokens": [
                    {"kind": "count", "value": "3"},
                    {"kind": "move", "key": "w"},
                    {"kind": "delete", "command": "x"},
                ],
                "concept": "counted-motion",
                "explanation": "Use a count for repeated motion.",
            }],
        })
        self.assertEqual(result[0]["compiledTokens"], ["3", "w", "x"])

    def test_rejects_conflicting_provider_fields(self):
        with self.assertRaises(ContractError):
            validate_response({
                "schemaVersion": 1,
                "candidates": [{
                    "tokens": [{"kind": "move", "key": "w", "value": "b"}],
                    "concept": "conflict",
                    "explanation": "Conflicting aliases are unsafe.",
                }],
            })


if __name__ == "__main__":
    unittest.main()
