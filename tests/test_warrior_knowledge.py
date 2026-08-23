from __future__ import annotations

import importlib.machinery
import importlib.util
import unittest
from pathlib import Path
from unittest.mock import patch


SCRIPT = Path(__file__).parents[1] / "bin" / "warrior-knowledge"
LOADER = importlib.machinery.SourceFileLoader("warrior_knowledge", str(SCRIPT))
SPEC = importlib.util.spec_from_loader(LOADER.name, LOADER)
MODULE = importlib.util.module_from_spec(SPEC)
LOADER.exec_module(MODULE)


class WarriorKnowledgeTest(unittest.TestCase):
    def test_reads_symbolic_remote_head(self):
        with patch.object(MODULE, "git", return_value=(
            0, "ref: refs/heads/main HEAD\nabc123\tHEAD", ""
        )):
            branch, error = MODULE.remote_default_branch(Path("/tmp/source"), "origin")
        self.assertEqual(branch, "main")
        self.assertIsNone(error)

    def test_inspection_fails_closed_on_dirty_or_divergent_source(self):
        answers = iter([
            (0, "true", ""),
            (0, "main", ""),
            (0, "aaaaaaaa", ""),
            (0, "?? notes.md", ""),
            (0, "ssh://git@example/repo.git", ""),
            (0, "bbbbbbbb\trefs/heads/main", ""),
        ])
        with patch.object(MODULE, "git", side_effect=lambda *args, **kwargs: next(answers)), \
             patch.object(MODULE, "remote_default_branch", return_value=("main", None)), \
             patch.object(MODULE.Path, "is_dir", return_value=True):
            report = MODULE.inspect(Path("/tmp/source"), "origin")
        self.assertFalse(report["healthy"])
        self.assertIn("knowledge source has uncommitted content", report["errors"])
        self.assertIn("local HEAD differs from remote default branch", report["errors"])

    def test_missing_source_is_unknown_not_healthy(self):
        report = MODULE.inspect(Path("/definitely/missing/knowledge"), "origin")
        self.assertFalse(report["healthy"])
        self.assertIn("does not exist", report["errors"][0])


if __name__ == "__main__":
    unittest.main()
