import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from worker.env import load_env_file


class EnvironmentFileTests(unittest.TestCase):
    def test_loads_project_values_without_overriding_shell(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / ".env"
            path.write_text(
                "# comment\n"
                "MODAL_API_KEY='from-file'\n"
                "export MODAL_BASE_URL=https://example.test/v1\n"
                "bad name=ignored\n",
                encoding="utf-8",
            )
            with patch.dict(os.environ, {"MODAL_API_KEY": "from-shell"}, clear=True):
                load_env_file(path)
                self.assertEqual(os.environ["MODAL_API_KEY"], "from-shell")
                self.assertEqual(os.environ["MODAL_BASE_URL"], "https://example.test/v1")
                self.assertNotIn("bad name", os.environ)


if __name__ == "__main__":
    unittest.main()
