from pathlib import Path
import tempfile
import unittest

from worker.vim_help import add_help_lessons, feature_catalog, help_summary


class VimHelpTests(unittest.TestCase):
    def test_feature_catalog_contains_tokens_and_local_documentation(self):
        with tempfile.TemporaryDirectory() as directory:
            runtime = Path(directory)
            docs = runtime / "doc"
            docs.mkdir()
            (docs / "tags").write_text("count\tintro.txt\t/*count*\n")
            (docs / "intro.txt").write_text(
                "\t\t*count*\n[count]\tA number repeats a command.\n"
            )
            count = next(item for item in feature_catalog(runtime) if item["helpTag"] == "count")
            self.assertEqual(count["token"], {"kind": "count", "value": "1-20"})
            self.assertEqual(count["documentation"], "A number repeats a command.")

    def test_extracts_first_documentation_sentence(self):
        with tempfile.TemporaryDirectory() as directory:
            runtime = Path(directory)
            docs = runtime / "doc"
            docs.mkdir()
            (docs / "tags").write_text("count\tintro.txt\t/*count*\n")
            (docs / "intro.txt").write_text(
                "\t\t*count*\n"
                "[count]\tAn optional number that may precede the command to multiply\n"
                "\t\tor iterate the command. More detail follows.\n"
            )
            self.assertEqual(
                help_summary("count", r"^\[count\]\s+", runtime),
                "An optional number that may precede the command to multiply or iterate the command.",
            )

    def test_replaces_ai_prose_with_local_help(self):
        with tempfile.TemporaryDirectory() as directory:
            runtime = Path(directory)
            docs = runtime / "doc"
            docs.mkdir()
            (docs / "tags").write_text("count\tintro.txt\t/*count*\n")
            (docs / "intro.txt").write_text(
                "\t\t*count*\n[count]\tA number before a command repeats the command.\n"
            )
            result = add_help_lessons([{
                "episodeId": 1,
                "candidates": [{
                    "tokens": [{"kind": "count", "value": 3}],
                    "concept": "AI title",
                    "explanation": "AI explanation",
                }],
            }], runtime)
            lesson = result[0]["candidates"][0]
            self.assertEqual(lesson["concept"], "Counts")
            self.assertEqual(lesson["explanation"], "A number before a command repeats the command.")
            self.assertEqual(lesson["helpTag"], "count")
            self.assertEqual(lesson["documentationSource"], "nvim-runtime-help")

    def test_selects_feature_introduced_by_candidate(self):
        with tempfile.TemporaryDirectory() as directory:
            runtime = Path(directory)
            docs = runtime / "doc"
            docs.mkdir()
            (docs / "tags").write_text("e\tmotion.txt\t/*e*\n")
            (docs / "motion.txt").write_text(
                "\t\t*e*\ne\tForward to the end of word [count] |inclusive|.\n"
            )
            result = add_help_lessons([{
                "episodeId": 1,
                "candidates": [{
                    "tokens": [
                        {"kind": "move", "key": "e"},
                        {"kind": "delete", "command": "x"},
                    ],
                    "originalTokens": ["l", "l", "l", "l", "x"],
                    "concept": "AI title",
                    "explanation": "AI explanation",
                }],
            }], runtime)
            lesson = result[0]["candidates"][0]
            self.assertEqual(lesson["concept"], "Move to the end of a word")
            self.assertEqual(lesson["helpTag"], "e")


if __name__ == "__main__":
    unittest.main()
