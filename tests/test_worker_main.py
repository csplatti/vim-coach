import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from worker.main import main
from worker.provider import LLMError


class WorkerMainTests(unittest.TestCase):
    def test_batch_falls_back_to_local_catalog_when_provider_is_unavailable(self):
        request = {
            "schemaVersion": 2,
            "cloudEnabled": True,
            "batchId": "batch-1",
            "episodes": [{"id": 1, "resolvedTokens": ["l", "l", "l", "l"]}],
        }
        verified = [{
            "episodeId": 1,
            "candidates": [{
                "tokens": [{"kind": "move", "key": "w"}],
                "compiledTokens": ["w"],
                "concept": "Move by words",
                "explanation": "Use a word motion.",
                "helpTag": "w",
                "_featureKey": "w",
            }],
        }]
        with tempfile.TemporaryDirectory() as directory, patch.dict(
            "os.environ", {
                "VIM_COACH_HISTORY_FILE": str(Path(directory) / "lessons.json"),
                "VIM_COACH_STATUS_FILE": str(Path(directory) / "status.json"),
            }, clear=True
        ), patch("sys.stdin", io.StringIO(json.dumps(request))), patch(
            "sys.stdout", new_callable=io.StringIO
        ) as stdout, patch(
            "worker.main.LLMConfig.from_env", side_effect=LLMError("provider unavailable")
        ), patch(
            "worker.main.augment_local_candidates", return_value=verified
        ), patch(
            "worker.main.verify_batch_candidates", return_value=verified
        ), patch(
            "worker.main.add_help_lessons", return_value=verified
        ):
            self.assertEqual(main(), 0)
            output = json.loads(stdout.getvalue())
        self.assertTrue(output["ok"])
        self.assertEqual(output["model"], "local-catalog")
        self.assertEqual(output["providerWarning"], "provider unavailable")
        self.assertEqual(output["persistedLessons"], 1)


if __name__ == "__main__":
    unittest.main()
