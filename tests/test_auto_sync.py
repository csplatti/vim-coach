from pathlib import Path
import shutil
import subprocess
import unittest


ROOT = Path(__file__).resolve().parents[1]


class AutoSyncTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which("nvim"), "Neovim is required")
    def test_single_flight_queue_pump(self):
        subprocess.run(
            [
                "nvim", "--headless", "-u", "NONE", "-i", "NONE", "-n",
                "--cmd", f"set rtp^={ROOT}",
                "-c", "lua dofile('tests/auto_sync_spec.lua')",
                "-c", "qa!",
            ],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )


if __name__ == "__main__":
    unittest.main()
