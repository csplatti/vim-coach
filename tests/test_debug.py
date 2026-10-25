import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from worker.debug import append_debug_event


class DebugLogTests(unittest.TestCase):
    def test_appends_jsonl_event(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "debug.jsonl"
            with patch.dict(os.environ, {"VIM_COACH_DEBUG_LOG_FILE": str(path)}):
                append_debug_event("llm_request", {"request": {"model": "test"}})
            event = json.loads(path.read_text().strip())
            self.assertEqual(event["kind"], "llm_request")
            self.assertEqual(event["payload"]["request"]["model"], "test")


if __name__ == "__main__":
    unittest.main()
