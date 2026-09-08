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

    def test_publish_refuses_on_blocking_errors_without_touching_git(self):
        unhealthy = {"healthy": False, "errors": ["knowledge source has uncommitted content"]}
        with patch.object(MODULE, "inspect", return_value=unhealthy), \
             patch.object(MODULE, "git") as git_mock:
            result = MODULE.publish(Path("/tmp/source"), "origin")
        self.assertEqual(result["action"], "refused")
        self.assertFalse(result["ok"])
        git_mock.assert_not_called()

    def test_publish_is_a_noop_when_already_in_sync(self):
        in_sync = {
            "healthy": True, "errors": [], "branch": "master",
            "head": "abc123", "remote_head": "abc123", "remote_default_branch": "master",
        }
        with patch.object(MODULE, "inspect", return_value=in_sync), \
             patch.object(MODULE, "git") as git_mock:
            result = MODULE.publish(Path("/tmp/source"), "origin")
        self.assertEqual(result, {"ok": True, "action": "already_published", "head": "abc123"})
        git_mock.assert_not_called()

    def test_publish_refuses_a_real_divergence_and_never_pushes(self):
        diverged = {
            "healthy": True,
            "errors": ["local HEAD differs from remote default branch"],
            "branch": "master", "head": "local123",
            "remote_head": "remote999", "remote_default_branch": "master",
        }
        with patch.object(MODULE, "inspect", return_value=diverged), \
             patch.object(MODULE, "_is_ancestor", return_value=False), \
             patch.object(MODULE, "git") as git_mock:
            result = MODULE.publish(Path("/tmp/source"), "origin")
        self.assertEqual(result["action"], "refused")
        self.assertFalse(result["ok"])
        self.assertIn("not a fast-forward", result["errors"][0])
        git_mock.assert_not_called()

    def test_publish_pushes_on_a_real_fast_forward_and_reverifies(self):
        ahead = {
            "healthy": True,
            "errors": ["local HEAD differs from remote default branch"],
            "branch": "master", "head": "local123",
            "remote_head": "remote999", "remote_default_branch": "master",
        }
        after = {**ahead, "healthy": True, "errors": [], "remote_head": "local123"}
        with patch.object(MODULE, "inspect", side_effect=[ahead, after]), \
             patch.object(MODULE, "_is_ancestor", return_value=True), \
             patch.object(MODULE, "git", return_value=(0, "", "")) as git_mock:
            result = MODULE.publish(Path("/tmp/source"), "origin")
        self.assertEqual(result["action"], "published")
        self.assertTrue(result["ok"])
        git_mock.assert_called_once_with(Path("/tmp/source"), "push", "origin", "master")

    def test_publish_reports_a_real_push_failure(self):
        ahead = {
            "healthy": True,
            "errors": ["local HEAD differs from remote default branch"],
            "branch": "master", "head": "local123",
            "remote_head": "remote999", "remote_default_branch": "master",
        }
        with patch.object(MODULE, "inspect", return_value=ahead), \
             patch.object(MODULE, "_is_ancestor", return_value=True), \
             patch.object(MODULE, "git", return_value=(1, "", "remote: permission denied")):
            result = MODULE.publish(Path("/tmp/source"), "origin")
        self.assertEqual(result["action"], "push_failed")
        self.assertFalse(result["ok"])
        self.assertIn("permission denied", result["errors"][0])

    def test_is_ancestor_true_when_commit_reachable_from_head(self):
        with patch.object(MODULE, "git", return_value=(0, "aaa\nbbb\nccc", "")):
            self.assertTrue(MODULE._is_ancestor(Path("/tmp/source"), "bbb"))

    def test_is_ancestor_false_when_commit_not_reachable(self):
        with patch.object(MODULE, "git", return_value=(0, "aaa\nbbb", "")):
            self.assertFalse(MODULE._is_ancestor(Path("/tmp/source"), "zzz"))

    def test_is_ancestor_none_when_rev_list_fails(self):
        with patch.object(MODULE, "git", return_value=(1, "", "fatal: bad revision")):
            self.assertIsNone(MODULE._is_ancestor(Path("/tmp/source"), "bbb"))


if __name__ == "__main__":
    unittest.main()
