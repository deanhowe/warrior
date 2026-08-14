"""Tests for warrior-facts.

The tool exists to keep work safe, so the tests are adversarial about the one
thing that matters: warrior-facts must never write. Three layers enforce it.

  1. Unit tests on the Git guard, which must refuse every mutating form.
  2. A source audit that reads this file's own AST and proves every literal
     `git(...)` call site in the tool would survive the guard, and that the
     tool has exactly one subprocess path that can invoke Git at all.
  3. A byte-for-byte snapshot of a real repository's .git directory taken
     before and after a full inspection. If any content changes, the test
     fails. The tool that prevents data loss must not cause it.
"""

from __future__ import annotations

import ast
import contextlib
import hashlib
import importlib.machinery
import importlib.util
import io
import json
import os
import subprocess
import tempfile
import unittest
from collections import Counter
from pathlib import Path

SCRIPT = Path(__file__).parents[1] / "bin" / "warrior-facts"
SPEC = importlib.util.spec_from_loader(
    "warrior_facts",
    importlib.machinery.SourceFileLoader("warrior_facts", str(SCRIPT)),
)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)

SOURCE = SCRIPT.read_text()

GIT_ENV = {
    **os.environ,
    "GIT_CONFIG_GLOBAL": os.devnull,
    "GIT_CONFIG_SYSTEM": os.devnull,
    "GIT_AUTHOR_NAME": "Warrior Test",
    "GIT_AUTHOR_EMAIL": "test@example.invalid",
    "GIT_COMMITTER_NAME": "Warrior Test",
    "GIT_COMMITTER_EMAIL": "test@example.invalid",
    "GIT_TERMINAL_PROMPT": "0",
}


def run_git(repo: Path, *args: str) -> str:
    """Test-only Git driver. The tool under test can never call this."""
    process = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True, text=True, check=True, env=GIT_ENV,
        stdin=subprocess.DEVNULL,
    )
    return process.stdout


def make_repo(path: Path, *, commit: bool = True, remote: str | None = None) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    run_git(path, "init", "-q", "-b", "main")
    if commit:
        (path / "README.md").write_text("hello\n")
        run_git(path, "add", "README.md")
        run_git(path, "commit", "-q", "-m", "initial")
    if remote:
        run_git(path, "remote", "add", "origin", remote)
    return path


@contextlib.contextmanager
def chdir(path: Path):
    previous = Path.cwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(previous)


def snapshot_tree(path: Path) -> dict[str, str]:
    """Content hash of every file under a directory."""
    entries: dict[str, str] = {}
    for current, _dirs, files in os.walk(path):
        for name in files:
            candidate = Path(current) / name
            try:
                entries[str(candidate.relative_to(path))] = hashlib.sha256(
                    candidate.read_bytes()
                ).hexdigest()
            except OSError:
                continue
    return entries


# ---------------------------------------------------------------------------


class GitGuardTest(unittest.TestCase):
    """The guard is the only thing standing between this tool and a mistake."""

    DESTRUCTIVE = [
        ("push",), ("push", "--force"), ("reset", "--hard"), ("clean", "-fd"),
        ("gc",), ("prune",), ("checkout", "main"), ("commit", "-m", "x"),
        ("add", "."), ("rm", "file"), ("mv", "a", "b"), ("fetch",),
        ("pull",), ("merge", "main"), ("rebase", "main"), ("switch", "main"),
        ("restore", "."), ("filter-branch",), ("update-ref", "HEAD", "x"),
        ("symbolic-ref", "HEAD", "refs/heads/x"), ("reflog", "expire"),
        ("worktree", "remove", "x"), ("worktree", "add", "x"),
        ("remote", "add", "origin", "url"), ("remote", "remove", "origin"),
        ("remote", "prune", "origin"), ("remote", "set-url", "origin", "url"),
        ("stash", "pop"), ("stash", "drop"), ("stash", "clear"),
        ("stash", "push"), ("branch", "-d", "topic"), ("branch", "-D", "topic"),
        ("config", "--unset", "user.name"),
    ]

    def test_refuses_every_destructive_form(self):
        for args in self.DESTRUCTIVE:
            with self.subTest(args=args):
                with self.assertRaises(RuntimeError):
                    MODULE.assert_read_only(args)

    def test_refuses_bare_stash_because_it_is_not_a_listing_command(self):
        # `git branch` and `git worktree` list when bare. `git stash` takes
        # work out of the working tree and reports only "ok stashed".
        with self.assertRaises(RuntimeError):
            MODULE.assert_read_only(("stash",))
        MODULE.assert_read_only(("stash", "list"))

    def test_refuses_no_subcommand(self):
        with self.assertRaises(RuntimeError):
            MODULE.assert_read_only(())

    def test_refuses_bare_forms_that_could_grow_a_verb(self):
        for args in [("remote",), ("status",), ("count-objects",)]:
            with self.subTest(args=args):
                with self.assertRaises(RuntimeError):
                    MODULE.assert_read_only(args)

    def test_refuses_denied_tokens_anywhere(self):
        for args in [
            ("log", "--force"), ("branch", "--list", "--delete"),
            ("status", "--porcelain", "--prune"), ("log", "-f"),
        ]:
            with self.subTest(args=args):
                with self.assertRaises(RuntimeError):
                    MODULE.assert_read_only(args)

    def test_allows_exactly_the_forms_the_tool_uses(self):
        allowed = [
            ("rev-parse", "--short=12", "HEAD"),
            ("rev-parse", "--abbrev-ref", "@{upstream}"),
            ("rev-parse", "--is-bare-repository"),
            ("branch", "--show-current"),
            ("status", "--porcelain=v1", "-z", "--no-renames"),
            ("stash", "list"),
            ("remote", "-v"),
            ("worktree", "list", "--porcelain"),
            ("log", "-1", "--format=%cI|%an|%s"),
        ]
        for args in allowed:
            with self.subTest(args=args):
                MODULE.assert_read_only(args)

    def test_git_wrapper_refuses_before_spawning_a_process(self):
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaises(RuntimeError):
                MODULE.git(Path(temporary), "push", "origin", "main")


class SourceAuditTest(unittest.TestCase):
    """Prove the guarantees from the source itself, not from the docstring."""

    def test_every_git_call_site_passes_the_guard(self):
        tree = ast.parse(SOURCE)
        sites = 0
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            if not (isinstance(node.func, ast.Name) and node.func.id == "git"):
                continue
            arguments = node.args[1:]
            self.assertTrue(
                all(isinstance(item, ast.Constant) and isinstance(item.value, str)
                    for item in arguments),
                f"git() call on line {node.lineno} builds arguments dynamically; "
                "every Git form in this tool must be a literal the audit can read",
            )
            MODULE.assert_read_only(tuple(item.value for item in arguments))
            sites += 1
        self.assertGreaterEqual(sites, 8, "expected the tool to inspect repositories")

    def test_only_one_subprocess_path_can_invoke_git(self):
        tree = ast.parse(SOURCE)
        git_invocations = []
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            if not (isinstance(node.func, ast.Attribute) and node.func.attr == "run"):
                continue
            if not node.args or not isinstance(node.args[0], ast.List):
                continue
            first = node.args[0].elts[0] if node.args[0].elts else None
            if isinstance(first, ast.Constant) and first.value == "git":
                git_invocations.append(node.lineno)
        self.assertEqual(1, len(git_invocations), f"found Git spawns at {git_invocations}")

    def test_git_calls_disable_index_writes_and_repository_supplied_programs(self):
        self.assertIn('"--no-optional-locks"', SOURCE)
        self.assertIn('"core.fsmonitor="', SOURCE)

    def test_no_mutating_git_verb_appears_in_the_allowlist(self):
        forbidden = {
            "push", "reset", "clean", "gc", "prune", "checkout", "commit",
            "add", "rm", "mv", "fetch", "pull", "merge", "rebase", "switch",
            "restore", "filter-branch", "update-ref", "symbolic-ref", "reflog",
            "apply", "am", "cherry-pick", "revert", "tag", "init", "clone",
        }
        self.assertFalse(forbidden & MODULE.READ_ONLY_GIT)


class RedactionTest(unittest.TestCase):
    def test_strips_embedded_credentials_from_remote_urls(self):
        redacted = MODULE.redact_remote("https://dean:hunter2@git.example.com/a/b.git")
        self.assertNotIn("hunter2", redacted)
        self.assertEqual("https://[REDACTED]@git.example.com/a/b.git", redacted)

    def test_strips_token_style_userinfo(self):
        redacted = MODULE.redact_remote("https://ghp_AAAABBBBCCCC@github.com/o/r.git")
        self.assertNotIn("ghp_AAAABBBBCCCC", redacted)

    def test_preserves_ssh_remotes_which_carry_no_secret(self):
        self.assertEqual(
            "git@github.com:owner/repo.git",
            MODULE.redact_remote("git@github.com:owner/repo.git"),
        )


class ProtectionTest(unittest.TestCase):
    def test_classifies_remote_transports(self):
        cases = {
            "git@github.com:o/r.git": "ssh",
            "ssh://git@host:2222/o/r.git": "ssh",
            "https://github.com/o/r.git": "https",
            "http://git.local:3030/o/r.git": "https",
            "git://host/o/r.git": "git",
            "/Users/developer/mirrors/r.git": "file",
            "file:///Users/developer/mirrors/r.git": "file",
            "../sibling.git": "file",
        }
        for url, expected in cases.items():
            with self.subTest(url=url):
                self.assertEqual(expected, MODULE.remote_transport(url))

    def test_no_remote_is_unprotected(self):
        self.assertEqual((False, "no_remote"), MODULE.protection_for([]))

    def test_filesystem_only_remotes_are_not_protection(self):
        # A filesystem path cannot push into a real Git server, and a
        # filesystem push into an up-to-date repository exits 0 having sent
        # nothing -- so it looks like it worked when it did not.
        remotes = [{"name": "backup", "url": "/Volumes/disk/r.git", "transport": "file"}]
        self.assertEqual((False, "local_path_remote_only"), MODULE.protection_for(remotes))

    def test_a_network_remote_counts_as_protection(self):
        remotes = [{"name": "origin", "url": "git@host:o/r.git", "transport": "ssh"}]
        protected, reason = MODULE.protection_for(remotes)
        self.assertTrue(protected)
        self.assertEqual("has_network_remote", reason)


class WalkTest(unittest.TestCase):
    def build(self, root: Path) -> None:
        (root / "app" / "src").mkdir(parents=True)
        (root / "app" / "node_modules" / "left-pad").mkdir(parents=True)
        (root / "app" / ".git").mkdir()
        (root / "app" / "package.json").write_text("{}")
        (root / ".ssh").mkdir()
        (root / ".ssh" / "id_ed25519").write_text("PRIVATE KEY")
        (root / "deep" / "one" / "two" / "three").mkdir(parents=True)

    def test_prunes_dependencies_credentials_and_depth(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            self.build(root)
            stats: Counter = Counter()
            seen = [
                path.relative_to(root).as_posix()
                for path, _d, _dirs, _files, _live in MODULE.walk_dirs(root, 3, stats)
            ]
            self.assertNotIn("app/node_modules", seen)
            self.assertNotIn("app/node_modules/left-pad", seen)
            self.assertNotIn(".ssh", seen)
            self.assertNotIn("app/.git", seen)
            self.assertNotIn("deep/one/two/three", seen)
            self.assertIn("app/src", seen)
            self.assertEqual(1, stats["sensitive"])
            self.assertGreaterEqual(stats["noisy"], 2)
            self.assertGreaterEqual(stats["depth_limit"], 1)

    def test_records_symlinks_without_following_them(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            outside = root.parent / (root.name + "-outside")
            outside.mkdir()
            (outside / "secret-project").mkdir()
            try:
                (root / "escape").symlink_to(outside, target_is_directory=True)
                stats: Counter = Counter()
                seen = [
                    str(path)
                    for path, _d, _dirs, _files, _live in MODULE.walk_dirs(root, 4, stats)
                ]
                self.assertEqual(1, stats["symlink"])
                self.assertFalse(any("secret-project" in item for item in seen))
                self.assertFalse(any(str(outside) in item for item in seen))
            finally:
                for child in outside.rglob("*"):
                    child.rmdir()
                outside.rmdir()

    def test_a_caller_can_stop_descent(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            (root / "top" / "below").mkdir(parents=True)
            stats: Counter = Counter()
            seen = []
            for path, _depth, _dirs, _files, live in MODULE.walk_dirs(root, 5, stats):
                seen.append(path.name)
                if path.name == "top":
                    live.clear()
            self.assertIn("top", seen)
            self.assertNotIn("below", seen)

    def test_identifies_repository_boundaries(self):
        self.assertEqual("git_worktree", MODULE.repo_kind(Path("/x"), {".git"}, set()))
        self.assertEqual("git_linked_worktree", MODULE.repo_kind(Path("/x"), set(), {".git"}))
        self.assertEqual(
            "bare_git", MODULE.repo_kind(Path("/x"), {"objects", "refs"}, {"HEAD"})
        )
        self.assertIsNone(MODULE.repo_kind(Path("/x"), {"src"}, {"README.md"}))


class WhereTest(unittest.TestCase):
    def test_scores_exact_above_prefix_above_substring(self):
        self.assertEqual((100, "exact"), MODULE.match_score("acme", "acme", "a/acme"))
        self.assertEqual((95, "exact_icase"), MODULE.match_score("acme", "ACME", "a/ACME"))
        self.assertEqual(
            (85, "exact_normalized"), MODULE.match_score("acme-vcs", "acme_vcs", "a/acme_vcs")
        )
        self.assertEqual((70, "prefix"), MODULE.match_score("acme", "acmeling", "a/acmeling"))
        self.assertEqual((50, "substring"), MODULE.match_score("oof", "acmeling", "a/acmeling"))
        self.assertIsNone(MODULE.match_score("zzz", "acme", "a/acme"))

    def test_a_query_with_a_slash_matches_the_path(self):
        self.assertEqual(
            (90, "path_suffix"), MODULE.match_score("VHOSTS/app", "app", "HERD/VHOSTS/app")
        )
        self.assertIsNone(MODULE.match_score("OTHER/app", "app", "HERD/VHOSTS/app"))

    def test_finds_a_project_and_reports_what_it_is(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            (root / "kingdom" / "warrior").mkdir(parents=True)
            (root / "kingdom" / "warrior" / ".git").mkdir()
            (root / "kingdom" / "warrior" / "README.md").write_text("x")
            (root / "kingdom" / "warrior-notes").mkdir()
            result, truncated = MODULE.find_where("warrior", [root], 4, 50)
            self.assertFalse(truncated)
            self.assertEqual(2, result["count"])
            best = result["matches"][0]
            self.assertEqual("warrior", best["name"])
            self.assertEqual("exact", best["match"])
            self.assertTrue(best["is_repo"])
            self.assertEqual(["README.md"], best["markers"])
            self.assertFalse(result["matches"][1]["is_repo"])

    def test_reports_nothing_rather_than_guessing(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            (root / "unrelated").mkdir()
            result, _ = MODULE.find_where("nowhere", [root], 4, 50)
            self.assertEqual(0, result["count"])
            self.assertEqual([], result["matches"])


class DiscoveryTest(unittest.TestCase):
    def test_finds_nested_and_bare_repositories_without_walking_object_stores(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            make_repo(root / "outer")
            make_repo(root / "outer" / "packages" / "inner")
            bare = root / "mirrors" / "thing.git"
            bare.mkdir(parents=True)
            (bare / "HEAD").write_text("ref: refs/heads/main\n")
            (bare / "objects" / "ab").mkdir(parents=True)
            (bare / "objects" / "ab" / "deadbeef").write_text("x")
            (bare / "refs").mkdir()

            records, _stats = MODULE.discover_repositories([root], 4)
            paths = {item["path"] for item in records}
            self.assertIn(str(root / "outer"), paths)
            self.assertIn(str(root / "outer" / "packages" / "inner"), paths)
            self.assertIn(str(bare), paths)
            kinds = {item["path"]: item["kind"] for item in records}
            self.assertEqual("bare_git", kinds[str(bare)])
            self.assertFalse(any("objects/ab" in item for item in paths))

    def test_flags_repositories_with_nowhere_else_to_live(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            make_repo(root / "orphan")
            make_repo(root / "mirrored", remote="git@example.invalid:o/r.git")
            make_repo(root / "disk-only", remote=str(root / "elsewhere.git"))

            result, _truncated = MODULE.survey_repositories([root], 3, 0, 4, True)
            by_path = {item["name"]: item for item in result["repositories"]}
            self.assertFalse(by_path["orphan"]["protected"])
            self.assertEqual("no_remote", by_path["orphan"]["protection"])
            self.assertTrue(by_path["mirrored"]["protected"])
            self.assertFalse(by_path["disk-only"]["protected"])
            self.assertEqual("local_path_remote_only", by_path["disk-only"]["protection"])
            self.assertEqual(2, result["unprotected_count"])

    def test_unprotected_filter_keeps_the_scanned_total(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            make_repo(root / "orphan")
            make_repo(root / "safe", remote="git@example.invalid:o/r.git")
            result, _ = MODULE.survey_repositories(
                [root], 3, 0, 4, True, only_unprotected=True
            )
            self.assertEqual(2, result["scanned"])
            self.assertEqual(1, result["count"])
            self.assertEqual("orphan", result["repositories"][0]["name"])

    def test_limit_truncates_the_list_but_not_the_count(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            for index in range(4):
                make_repo(root / f"repo{index}")
            result, truncated = MODULE.survey_repositories([root], 3, 2, 4, False)
            self.assertTrue(truncated)
            self.assertEqual(4, result["count"])
            self.assertEqual(2, len(result["repositories"]))


class StatusParsingTest(unittest.TestCase):
    def test_counts_staged_modified_and_untracked_separately(self):
        payload = "M  staged.txt\0 M modified.txt\0MM both.txt\0?? new file.txt\0"
        self.assertEqual(
            {"staged": 2, "modified": 2, "untracked": 1},
            MODULE.parse_status_counts(payload),
        )

    def test_handles_paths_containing_spaces(self):
        payload = "?? a file with spaces.txt\0"
        self.assertEqual(1, MODULE.parse_status_counts(payload)["untracked"])

    def test_empty_status_is_a_clean_tree(self):
        self.assertEqual(
            {"staged": 0, "modified": 0, "untracked": 0},
            MODULE.parse_status_counts(""),
        )


class RepositoryInspectionTest(unittest.TestCase):
    def test_reports_branch_head_dirt_stashes_and_nesting(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            repo = make_repo(root / "project", remote="git@example.invalid:o/r.git")
            make_repo(repo / "vendored-thing")
            (repo / "README.md").write_text("changed\n")
            (repo / "staged.txt").write_text("s\n")
            run_git(repo, "add", "staged.txt")
            (repo / "untracked.txt").write_text("u\n")
            (repo / "to-stash.txt").write_text("stash me\n")
            run_git(repo, "add", "to-stash.txt")
            run_git(repo, "stash", "push", "-q", "-m", "safety net", "--", "to-stash.txt")

            report = MODULE.inspect_repository(repo)
            self.assertEqual("main", report["branch"])
            self.assertFalse(report["detached"])
            self.assertEqual(12, len(report["head"]))
            self.assertEqual(1, report["counts"]["staged"])
            self.assertEqual(1, report["counts"]["modified"])
            # Two untracked entries: untracked.txt, and the nested repository,
            # which the outer repository reports as a single opaque entry. The
            # outer status says nothing about what is inside it -- which is
            # exactly why nested_repositories is reported separately.
            self.assertEqual(2, report["counts"]["untracked"])
            self.assertEqual(1, report["stash_entries"])
            self.assertFalse(report["clean"])
            self.assertTrue(report["protected"])
            self.assertEqual(
                [str(repo / "vendored-thing")], report["nested_repositories"]
            )
            self.assertIsNotNone(report["last_commit"])
            joined = " ".join(report["advice"])
            self.assertIn("committed objects only", joined)
            self.assertIn("Stashes are invisible", joined)
            self.assertIn("nested", joined)

    def test_resolves_the_repository_from_a_path_inside_it(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            repo = make_repo(root / "project")
            (repo / "src" / "deep").mkdir(parents=True)
            report = MODULE.inspect_repository(repo / "src" / "deep")
            self.assertEqual(str(repo), report["path"])

    def test_returns_nothing_outside_a_repository(self):
        with tempfile.TemporaryDirectory() as temporary:
            plain = Path(temporary).resolve() / "plain"
            plain.mkdir()
            # Guard against the temp dir living inside someone's repository.
            if MODULE.enclosing_repo(plain) is None:
                self.assertIsNone(MODULE.inspect_repository(plain))

    def test_names_a_detached_head_as_a_risk(self):
        with tempfile.TemporaryDirectory() as temporary:
            repo = make_repo(Path(temporary).resolve() / "project")
            head = run_git(repo, "rev-parse", "HEAD").strip()
            run_git(repo, "checkout", "-q", head)
            report = MODULE.inspect_repository(repo)
            self.assertTrue(report["detached"])
            self.assertIsNone(report["branch"])
            self.assertTrue(any("detached" in item for item in report["advice"]))

    def test_never_prints_a_credential_from_a_remote(self):
        with tempfile.TemporaryDirectory() as temporary:
            repo = make_repo(
                Path(temporary).resolve() / "project",
                remote="https://dean:hunter2@git.example.invalid/o/r.git",
            )
            report = MODULE.inspect_repository(repo)
            self.assertNotIn("hunter2", json.dumps(report))
            self.assertIn("[REDACTED]", report["remotes"][0]["url"])


class WritesNothingTest(unittest.TestCase):
    """The tool built to prevent data loss must not cause any."""

    def test_a_full_inspection_leaves_the_git_directory_byte_identical(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            repo = make_repo(root / "project", remote="git@example.invalid:o/r.git")
            (repo / "README.md").write_text("dirty\n")
            (repo / "untracked.txt").write_text("u\n")
            (repo / "staged.txt").write_text("s\n")
            run_git(repo, "add", "staged.txt")

            before = snapshot_tree(repo / ".git")
            self.assertIn("index", before)

            MODULE.inspect_repository(repo)
            MODULE.discover_repositories([root], 3)
            MODULE.read_remotes(repo)

            after = snapshot_tree(repo / ".git")
            changed = sorted(
                name for name in set(before) | set(after)
                if before.get(name) != after.get(name)
            )
            self.assertEqual([], changed, f"warrior-facts modified: {changed}")

    def test_inspection_does_not_run_repository_supplied_hooks(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            repo = make_repo(root / "project")
            evidence = root / "hook-ran.txt"
            hook = repo / ".git" / "hooks" / "post-index-change"
            hook.write_text(f"#!/bin/sh\necho ran > {evidence}\n")
            hook.chmod(0o755)
            (repo / "README.md").write_text("dirty\n")

            MODULE.inspect_repository(repo)
            self.assertFalse(
                evidence.exists(),
                "git status refreshed the index and executed a repository-supplied hook",
            )


class ToolchainTest(unittest.TestCase):
    def test_refuses_to_execute_a_binary_from_inside_the_working_tree(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            (root / "node_modules" / ".bin").mkdir(parents=True)
            planted = root / "node_modules" / ".bin" / "node"
            planted.write_text("#!/bin/sh\nexit 0\n")
            planted.chmod(0o755)
            with chdir(root):
                self.assertFalse(MODULE.trusted_executable(planted))
                self.assertTrue(MODULE.trusted_executable(Path("/bin/sh")))

    def test_reports_presence_without_probing_when_asked(self):
        record = MODULE.probe_tool(("git", "vcs", ("--version",)), with_versions=False)
        self.assertIsNotNone(record)
        self.assertIsNone(record["version"])
        self.assertIn("not probed", record["version_note"])

    def test_missing_tools_are_reported_as_absent_not_invented(self):
        self.assertIsNone(
            MODULE.probe_tool(("definitely-not-installed-xyz", "language", ("--version",)), True)
        )

    def test_survey_finds_git_and_python_on_any_developer_machine(self):
        result = MODULE.survey_toolchains(with_versions=False, workers=4)
        names = {tool["name"] for tool in result["tools"]}
        self.assertIn("git", names)
        self.assertIn("python3", names)
        self.assertIn("vcs", result["by_category"])


class ServicesTest(unittest.TestCase):
    LSOF = (
        "COMMAND PID USER FD TYPE DEVICE SIZE/OFF NODE NAME\n"
        "node    111 dean 20u IPv4 0x1 0t0 TCP *:3000 (LISTEN)\n"
        "node    111 dean 21u IPv6 0x2 0t0 TCP *:3000 (LISTEN)\n"
        "postgres 222 dean 5u IPv4 0x3 0t0 TCP 127.0.0.1:5432 (LISTEN)\n"
    )

    def test_parses_lsof_and_groups_by_port_and_process(self):
        rows = MODULE.parse_lsof(self.LSOF)
        self.assertEqual(3, len(rows))
        self.assertEqual(3000, rows[0]["port"])
        self.assertEqual("node", rows[0]["process"])
        self.assertEqual(5432, rows[2]["port"])

    def test_parses_ss_output_with_process_information(self):
        payload = (
            'LISTEN 0 511 127.0.0.1:6379 0.0.0.0:* users:(("redis-server",pid=9,fd=6))\n'
        )
        rows = MODULE.parse_ss(payload)
        self.assertEqual(1, len(rows))
        self.assertEqual(6379, rows[0]["port"])
        self.assertEqual("redis-server", rows[0]["process"])
        self.assertEqual("9", rows[0]["pid"])

    def test_survey_reports_real_sockets_with_scope_and_hints(self):
        result, _warnings = MODULE.survey_services()
        self.assertEqual("tcp", result["protocol"])
        self.assertIsInstance(result["count"], int)
        for service in result["services"]:
            self.assertIn(service["scope"], {"loopback", "all_interfaces", "specific_interface"})
            self.assertIsInstance(service["port"], int)

    def test_port_hints_describe_common_dev_services(self):
        self.assertEqual("postgresql", MODULE.PORT_HINTS[5432])
        self.assertEqual("vite dev server", MODULE.PORT_HINTS[5173])


class RootsTest(unittest.TestCase):
    def test_drops_roots_contained_in_other_roots(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            (root / "outer" / "inner").mkdir(parents=True)
            kept = MODULE.dedupe_roots([root / "outer", root / "outer" / "inner"])
            self.assertEqual([root / "outer"], kept)

    def test_reports_a_root_that_does_not_exist_rather_than_ignoring_it(self):
        roots, warnings = MODULE.resolve_roots(["/definitely/not/here"])
        self.assertEqual([], roots)
        self.assertTrue(any("Not a directory" in item for item in warnings))

    def test_environment_can_name_the_roots(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            (root / "work").mkdir()
            previous = os.environ.get("WARRIOR_ROOTS")
            os.environ["WARRIOR_ROOTS"] = str(root / "work")
            try:
                self.assertIn(root / "work", MODULE.default_roots())
            finally:
                if previous is None:
                    os.environ.pop("WARRIOR_ROOTS")
                else:
                    os.environ["WARRIOR_ROOTS"] = previous


class ContractTest(unittest.TestCase):
    """The JSON shape is what an agent depends on. Keep it stable and small."""

    def run_cli(self, argv: list[str]) -> tuple[int, dict]:
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer), contextlib.redirect_stderr(io.StringIO()):
            code = MODULE.main(argv)
        return code, json.loads(buffer.getvalue())

    def test_envelope_is_the_documented_shape(self):
        code, payload = self.run_cli(["--json", "schema"])
        self.assertEqual(MODULE.EXIT_OK, code)
        for key in ("schema_version", "tool", "command", "read_only",
                    "generated_at", "elapsed_seconds", "truncated", "warnings", "result"):
            self.assertIn(key, payload)
        self.assertEqual(1, payload["schema_version"])
        self.assertEqual("warrior-facts", payload["tool"])
        self.assertTrue(payload["read_only"])

    def test_schema_documents_every_command(self):
        _code, payload = self.run_cli(["--json", "schema"])
        documented = set(payload["result"]["commands"])
        implemented = set(MODULE.RENDERERS) - {"schema"}
        self.assertEqual(implemented, documented)

    def test_where_returns_exit_one_when_the_answer_is_nothing(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            (root / "something").mkdir()
            code, payload = self.run_cli(
                ["--json", "--root", str(root), "where", "no-such-project"]
            )
            self.assertEqual(MODULE.EXIT_NOT_FOUND, code)
            self.assertEqual(0, payload["result"]["count"])

    def test_repo_outside_a_repository_returns_exit_one_and_still_valid_json(self):
        with tempfile.TemporaryDirectory() as temporary:
            plain = Path(temporary).resolve()
            if MODULE.enclosing_repo(plain) is not None:
                self.skipTest("temporary directory is inside a repository")
            code, payload = self.run_cli(["--json", "repo", str(plain)])
            self.assertEqual(MODULE.EXIT_NOT_FOUND, code)
            self.assertFalse(payload["result"]["found"])
            self.assertTrue(payload["warnings"])

    def test_human_output_is_produced_for_every_command_shape(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            make_repo(root / "project")
            for argv in (
                ["--root", str(root), "where", "project"],
                ["--root", str(root), "repos"],
                ["--root", str(root), "unprotected"],
                ["repo", str(root / "project")],
                ["--no-versions", "toolchains"],
                ["services"],
            ):
                with self.subTest(argv=argv):
                    buffer = io.StringIO()
                    with contextlib.redirect_stdout(buffer), \
                            contextlib.redirect_stderr(io.StringIO()):
                        MODULE.main(argv)
                    self.assertTrue(buffer.getvalue().strip())

    def test_orient_bundles_a_cold_start_answer(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            make_repo(root / "project")
            code, payload = self.run_cli(["--json", "--root", str(root), "orient"])
            self.assertEqual(MODULE.EXIT_OK, code)
            result = payload["result"]
            for key in ("host", "roots", "repositories", "toolchains",
                        "services", "current_repository"):
                self.assertIn(key, result)
            self.assertEqual(1, result["repositories"]["count"])
            self.assertEqual(1, result["repositories"]["unprotected_count"])

    def test_orient_fits_in_a_context_window(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            for index in range(30):
                make_repo(root / f"repo{index}")
            buffer = io.StringIO()
            with contextlib.redirect_stdout(buffer), contextlib.redirect_stderr(io.StringIO()):
                MODULE.main(["--json", "--root", str(root), "orient"])
            self.assertLess(len(buffer.getvalue()), 20_000)

    def test_rejects_an_out_of_range_depth(self):
        with self.assertRaises(SystemExit) as raised:
            with contextlib.redirect_stderr(io.StringIO()):
                MODULE.main(["--max-depth", "99", "repos"])
        self.assertEqual(MODULE.EXIT_USAGE, raised.exception.code)


if __name__ == "__main__":
    unittest.main(verbosity=2)
