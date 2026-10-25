import json
from pathlib import Path
import tempfile
import unittest

from worker.history import append_verified_lessons, related_lessons, reset_lesson_statuses, update_lesson_status


class HistoryTests(unittest.TestCase):
    def test_persists_verified_metadata_without_source_snapshots(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "lessons.json"
            count = append_verified_lessons(path, [{
                "episodeId": 5,
                "candidates": [{
                    "tokens": [{"kind": "move", "key": "w"}],
                    "compiledTokens": ["w"],
                    "concept": "word-motion",
                    "explanation": "Move by word.",
                    "originalLogicalKeys": 3,
                    "candidateLogicalKeys": 1,
                    "savedLogicalKeys": 2,
                    "verification": {"accepted": True},
                }],
            }], "test-model", created_at="2026-10-24T00:00:00+00:00")
            self.assertEqual(count, 1)
            value = json.loads(path.read_text())
            self.assertEqual(value["schemaVersion"], 1)
            self.assertEqual(value["lessons"][0]["episodeId"], 5)
            self.assertNotIn("before", value["lessons"][0])
            self.assertNotIn("after", value["lessons"][0])
            self.assertEqual(value["lessons"][0]["status"], "new")
            lesson_id = value["lessons"][0]["lessonId"]
            self.assertTrue(update_lesson_status(path, lesson_id, "known"))
            self.assertEqual(json.loads(path.read_text())["lessons"][0]["status"], "known")
            self.assertEqual(reset_lesson_statuses(path), 1)
            self.assertEqual(json.loads(path.read_text())["lessons"][0]["status"], "new")
            context = related_lessons(path, [{"resolvedTokens": ["w", "x"]}])
            self.assertEqual(context[0]["concept"], "word-motion")
            self.assertIn("helpTag", context[0])
            self.assertNotIn("before", context[0])

    def test_does_not_persist_duplicate_help_tag(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "lessons.json"
            first = [{
                "episodeId": 1,
                "candidates": [{
                    "tokens": [{"kind": "count", "value": 3}],
                    "compiledTokens": ["3", "w"],
                    "concept": "Counts",
                    "explanation": "Use a count.",
                    "helpTag": "count",
                }],
            }]
            second = [{
                "episodeId": 2,
                "candidates": [{
                    "tokens": [{"kind": "count", "value": 5}],
                    "compiledTokens": ["5", "h"],
                    "concept": "Counts",
                    "explanation": "Use a count.",
                    "helpTag": "count",
                }],
            }]
            self.assertEqual(append_verified_lessons(path, first, "model"), 1)
            self.assertEqual(append_verified_lessons(path, second, "model"), 0)
            self.assertEqual(len(json.loads(path.read_text())["lessons"]), 1)


if __name__ == "__main__":
    unittest.main()
