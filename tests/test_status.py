import json
from pathlib import Path
import tempfile
import unittest

from worker.status import write_status


class StatusTests(unittest.TestCase):
    def test_writes_batch_state_without_source_data(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "status.json"
            old_path = __import__("os").environ.get("VIM_COACH_STATUS_FILE")
            __import__("os").environ["VIM_COACH_STATUS_FILE"] = str(path)
            try:
                write_status("running", "batch-1", episodeCount=3)
                value = json.loads(path.read_text())
            finally:
                if old_path is None:
                    __import__("os").environ.pop("VIM_COACH_STATUS_FILE", None)
                else:
                    __import__("os").environ["VIM_COACH_STATUS_FILE"] = old_path
            self.assertEqual(value["state"], "running")
            self.assertEqual(value["batchId"], "batch-1")
            self.assertEqual(value["episodeCount"], 3)
            self.assertNotIn("before", value)


if __name__ == "__main__":
    unittest.main()
