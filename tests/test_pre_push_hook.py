from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from pathlib import Path


HOOK = Path(__file__).parents[1] / "hooks" / "pre-push-preservation"
ENV = {
    **os.environ,
    "GIT_AUTHOR_NAME": "Warrior Test",
    "GIT_AUTHOR_EMAIL": "test@example.invalid",
    "GIT_COMMITTER_NAME": "Warrior Test",
    "GIT_COMMITTER_EMAIL": "test@example.invalid",
    "GIT_CONFIG_GLOBAL": os.devnull,
    "GIT_CONFIG_SYSTEM": os.devnull,
}
ZERO = "0" * 40


class PreservationPrePushHookTest(unittest.TestCase):
    def test_allows_new_and_fast_forward_refs_but_blocks_rewrite_and_delete(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repo = Path(temporary)
            subprocess.run(["git", "init", "-q", "-b", "main", str(repo)], check=True, env=ENV)
            (repo / "file").write_text("one\n")
            subprocess.run(["git", "-C", str(repo), "add", "file"], check=True, env=ENV)
            subprocess.run(["git", "-C", str(repo), "commit", "-q", "-m", "one"], check=True, env=ENV)
            old = subprocess.check_output(["git", "-C", str(repo), "rev-parse", "HEAD"], text=True, env=ENV).strip()
            (repo / "file").write_text("two\n")
            subprocess.run(["git", "-C", str(repo), "commit", "-qam", "two"], check=True, env=ENV)
            new = subprocess.check_output(["git", "-C", str(repo), "rev-parse", "HEAD"], text=True, env=ENV).strip()

            def invoke(line: str) -> subprocess.CompletedProcess[str]:
                return subprocess.run(
                    [str(HOOK), "origin", "ssh://git@example.invalid/dean/repo.git"],
                    cwd=repo,
                    input=line,
                    capture_output=True,
                    text=True,
                    env=ENV,
                )

            self.assertEqual(invoke(f"refs/heads/main {new} refs/heads/main {ZERO}\n").returncode, 0)
            self.assertEqual(invoke(f"refs/heads/main {new} refs/heads/main {old}\n").returncode, 0)
            self.assertNotEqual(invoke(f"refs/heads/main {old} refs/heads/main {new}\n").returncode, 0)
            self.assertNotEqual(invoke(f"(delete) {ZERO} refs/heads/main {new}\n").returncode, 0)


if __name__ == "__main__":
    unittest.main()
