import unittest

from worker.contracts import ContractError, compile_tokens, validate_response


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


if __name__ == "__main__":
    unittest.main()
