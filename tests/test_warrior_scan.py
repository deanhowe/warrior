import ast
import importlib.machinery
import importlib.util
import os
import re
import subprocess
import sys
import tempfile
import unittest
import unittest.mock
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "bin" / "warrior-scan"
SPEC = importlib.util.spec_from_loader(
    "warrior_scan",
    importlib.machinery.SourceFileLoader("warrior_scan", str(SCRIPT)),
)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)

SOURCE = SCRIPT.read_text()

# Verbs that take work out of the working tree, the index, the object store or
# the reflog. None of these may appear as a quoted argument anywhere in the
# scanner, and none may survive the guard at runtime.
DESTRUCTIVE_VERBS = (
    "add am apply cherry-pick checkout clean clone commit fetch filter-branch gc "
    "init merge mv prune pull rebase repack reset restore revert rm submodule "
    "switch tag update-ref"
).split()
# "commit" is also an ordinary English noun and appears in the evidence prose
# ("the only copy of 19 commits"). The literal-text sweep therefore skips it and
# the AST sweep below proves it is never passed to Git as an argument.
TEXT_SCAN_VERBS = [verb for verb in DESTRUCTIVE_VERBS if verb != "commit"]


def git_call_arguments() -> list[tuple[int, str]]:
    """Every string literal handed to the module's git() choke point, in order."""
    literals = []
    for node in ast.walk(ast.parse(SOURCE)):
        if not isinstance(node, ast.Call):
            continue
        if not (isinstance(node.func, ast.Name) and node.func.id == "git"):
            continue
        for position, argument in enumerate(node.args[1:]):
            if isinstance(argument, ast.Constant) and isinstance(argument.value, str):
                literals.append((position, argument.value))
    return literals


def run_git(repo: Path, *args: str) -> None:
    """Build fixtures with real Git; the scanner itself never gets to do this."""
    subprocess.run(
        ["git", "-C", str(repo), *args],
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        check=True,
        env={
            "PATH": "/usr/bin:/bin:/usr/local/bin",
            "HOME": str(repo),
            "GIT_AUTHOR_NAME": "Fixture",
            "GIT_AUTHOR_EMAIL": "fixture@example.invalid",
            "GIT_COMMITTER_NAME": "Fixture",
            "GIT_COMMITTER_EMAIL": "fixture@example.invalid",
            "GIT_CONFIG_GLOBAL": "/dev/null",
            "GIT_CONFIG_SYSTEM": "/dev/null",
        },
    )


class SeverityTest(unittest.TestCase):
    def test_ranks_invisible_single_copies_above_everything_else(self):
        self.assertEqual("CRITICAL", MODULE.severity_for("V1"))
        self.assertEqual("CRITICAL", MODULE.severity_for("V6"))

    def test_untracked_is_critical_only_when_the_repository_has_no_remote(self):
        self.assertEqual("CRITICAL", MODULE.severity_for("V5", {"has_remote": False}))
        self.assertEqual("HIGH", MODULE.severity_for("V5", {"has_remote": True}))

    def test_single_copy_is_high_and_expiring_copies_are_medium(self):
        self.assertEqual("HIGH", MODULE.severity_for("V3"))
        self.assertEqual("HIGH", MODULE.severity_for("V7"))
        self.assertEqual("MEDIUM", MODULE.severity_for("V2"))
        self.assertEqual("MEDIUM", MODULE.severity_for("V4"))

    def test_structural_vectors_are_informational(self):
        for vector in ("V8", "V9", "V10", "V11"):
            self.assertEqual("INFO", MODULE.severity_for(vector), vector)

    def test_every_vector_has_a_name_and_a_rankable_severity(self):
        for vector in MODULE.VECTOR_NAMES:
            self.assertIn(MODULE.severity_for(vector), MODULE.SEVERITY_RANK)
        self.assertEqual(11, len(MODULE.VECTOR_NAMES))


class RedactionTest(unittest.TestCase):
    def test_redacts_embedded_remote_credentials(self):
        line = "origin\thttps://user:hunter2@git.example.invalid/team/app.git (fetch)"
        self.assertEqual(
            "origin\thttps://[REDACTED]@git.example.invalid/team/app.git (fetch)",
            MODULE.redact_remote(line),
        )

    def test_preserves_ssh_remote(self):
        line = "backup\tssh://git@git.example.invalid:2222/team/app.git (fetch)"
        self.assertEqual("backup\tssh://[REDACTED]@git.example.invalid:2222/team/app.git (fetch)",
                         MODULE.redact_remote(line))
        scp_style = "origin\tgit@github.com:team/app.git (fetch)"
        self.assertEqual(scp_style, MODULE.redact_remote(scp_style))

    def test_withholds_filename_samples_from_private_financial_trees(self):
        self.assertTrue(MODULE.SAMPLE_WITHHELD.search("/somewhere/projects/site/.tax"))
        self.assertTrue(MODULE.SAMPLE_WITHHELD.search("/home/x/secrets"))
        self.assertIsNone(MODULE.SAMPLE_WITHHELD.search("/somewhere/projects/site"))


class StatusParsingTest(unittest.TestCase):
    def test_reads_the_xy_field_positionally_and_consumes_rename_sources(self):
        payload = "AD packages/.gitignore\0 D apps/vhosts/playground\0?? notes.md\0"
        records = MODULE.parse_status(payload)
        self.assertEqual(
            [("A", "D", "packages/.gitignore"), (" ", "D", "apps/vhosts/playground"),
             ("?", "?", "notes.md")],
            [(item["x"], item["y"], item["path"]) for item in records],
        )

    def test_rename_source_path_is_not_mistaken_for_an_entry(self):
        payload = "R  new name.md\0old name.md\0?? kept.md\0"
        records = MODULE.parse_status(payload)
        self.assertEqual(["new name.md", "kept.md"], [item["path"] for item in records])

    def test_build_debris_is_separated_from_work_but_tmp_never_is(self):
        self.assertTrue(MODULE.build_debris("node_modules/left-pad/index.js"))
        self.assertTrue(MODULE.build_debris("DerivedData/"))
        self.assertFalse(MODULE.build_debris("tmp/work-in-progress.md"))
        self.assertFalse(MODULE.build_debris("app/Events/ShaderControlEvent.php"))


class SymlinkDedupeTest(unittest.TestCase):
    def test_symlinked_root_resolves_to_one_scan_and_is_reported_not_hidden(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            real = root / "workspace"
            real.mkdir()
            alias = root / "workspace-alias"
            alias.symlink_to(real, target_is_directory=True)

            roots, findings = MODULE.dedupe_roots([alias, real])
            self.assertEqual([real], roots)
            self.assertEqual(["V8", "V8"], [item["vector"] for item in findings])
            self.assertTrue(any("same tree" in item["evidence"] for item in findings))
            self.assertTrue(all(item["severity"] == "INFO" for item in findings))

    def test_a_merely_relative_root_is_not_mistaken_for_an_alias(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            (root / "plain").mkdir()
            roots, findings = MODULE.dedupe_roots([root / "plain"])
            self.assertEqual([root / "plain"], roots)
            self.assertEqual([], findings)

    def test_symlink_inside_the_tree_is_recorded_with_its_target(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            (root / "real").mkdir()
            (root / "real" / ".git").mkdir()
            link = root / "alias"
            link.symlink_to(root / "real", target_is_directory=True)

            findings = MODULE.symlink_findings([link], [root])
            self.assertEqual(1, len(findings))
            self.assertEqual("V8", findings[0]["vector"])
            self.assertTrue(findings[0]["detail"]["target_is_repository"])
            self.assertEqual(str(root / "real"), findings[0]["detail"]["target"])


class ShelfDetectionTest(unittest.TestCase):
    def _tree(self, root: Path) -> None:
        modern = root / "app" / ".idea" / "shelf" / "Uncommitted_changes_[Changes]"
        modern.mkdir(parents=True)
        (modern / "shelved.patch").write_text("--- a/x\n+++ b/x\n")
        legacy = root / "app" / ".idea" / "shelf"
        (legacy / "old_change.patch").write_text("--- a/y\n+++ b/y\n")
        (legacy / "old_change.xml").write_text("<changelist/>")
        vendored = root / "app" / "node_modules" / "less-loader" / ".idea" / "shelf"
        vendored.mkdir(parents=True)
        (vendored / "upstream.patch").write_text("--- a/z\n+++ b/z\n")

    def test_finds_modern_and_legacy_shelves_and_skips_vendor_trees_by_default(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            self._tree(root)
            hits = MODULE.shelf_patches(root, 12, include_vendor=False)
            names = sorted(Path(item["path"]).name for item in hits)
            self.assertEqual(["old_change.patch", "shelved.patch"], names)
            self.assertTrue(all(not item["vendored"] for item in hits))
            self.assertNotIn("old_change.xml", [Path(item["path"]).name for item in hits])

    def test_vendor_shelves_are_found_only_on_request_and_ranked_down(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            self._tree(root)
            hits = MODULE.shelf_patches(root, 12, include_vendor=True)
            self.assertEqual(3, len(hits))
            findings = {Path(item["path"]).name: item for item in MODULE.shelf_findings(hits)}
            self.assertEqual("CRITICAL", findings["shelved.patch"]["severity"])
            self.assertEqual("INFO", findings["upstream.patch"]["severity"])
            self.assertIn("vendored package", findings["upstream.patch"]["evidence"])

    def test_shelf_scan_reaches_deeper_than_the_repository_walk(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            deep = root / "a" / "b" / "c" / "d" / "e" / "f" / ".idea" / "shelf"
            deep.mkdir(parents=True)
            (deep / "shelved.patch").write_text("--- a/x\n")
            self.assertEqual(1, len(MODULE.shelf_patches(root, 12, include_vendor=False)))
            self.assertEqual([], MODULE.shelf_patches(root, 2, include_vendor=False))


class BareRepositoryTest(unittest.TestCase):
    def test_bare_repository_is_inspected_at_object_level_not_as_a_worktree(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            work = root / "work"
            work.mkdir()
            run_git(work, "init", "-q", "-b", "main")
            (work / "note.md").write_text("work\n")
            run_git(work, "add", "note.md")
            run_git(work, "commit", "-qm", "first")
            bare = root / "store.git"
            subprocess.run(
                ["git", "clone", "-q", "--bare", str(work), str(bare)],
                stdin=subprocess.DEVNULL, capture_output=True, check=True,
            )

            entries = MODULE.candidate_repositories([bare])
            self.assertEqual([bare], entries)
            resolved, errors = MODULE.resolve_repositories([bare])
            self.assertEqual([], errors)
            self.assertEqual(1, len(resolved))
            self.assertTrue(resolved[0]["bare"])

            findings = MODULE.bare_findings(bare)
            self.assertEqual("V10", findings[0]["vector"])
            self.assertEqual("INFO", findings[0]["severity"])
            self.assertIn("bare repository", findings[0]["evidence"])
            self.assertIn("main", findings[0]["evidence"])
            # status is never attempted against a bare repository
            self.assertEqual([], MODULE.status_findings(bare, True)[0])

    def test_forge_object_store_mirrors_are_catalogued_not_counted_as_work_at_risk(self):
        repositories = [
            {"path": Path("/x/srv/gitea/repositories/team/a.git"), "bare": True, "git_dir": "a"},
            {"path": Path("/x/srv/gitea/repositories/team/b.git"), "bare": True, "git_dir": "b"},
            {"path": Path("/x/projects/ops.git"), "bare": True, "git_dir": "c"},
            {"path": Path("/x/projects/app"), "bare": False, "git_dir": "d"},
        ]
        active, stores, findings = MODULE.partition_forge_stores(repositories)
        self.assertEqual(
            ["/x/projects/app", "/x/projects/ops.git"],
            sorted(str(item["path"]) for item in active),
        )
        self.assertEqual({"/x/srv/gitea": 2}, stores)
        self.assertEqual("V10", findings[0]["vector"])
        self.assertFalse(findings[0]["detail"]["evaluated"])

    def test_forge_exclusion_is_inert_on_a_machine_with_no_forge(self):
        """The port must work where no Gitea and no Moof exist at all."""
        repositories = [
            {"path": Path("/x/projects/app.git"), "bare": True, "git_dir": "a"},
            {"path": Path("/x/projects/app"), "bare": False, "git_dir": "b"},
        ]
        active, stores, findings = MODULE.partition_forge_stores(repositories)
        self.assertEqual(2, len(active))
        self.assertEqual({}, stores)
        self.assertEqual([], findings)

    def test_a_declared_forge_root_is_honoured_wherever_it_lives(self):
        repositories = [
            {"path": Path("/srv/vcs/store/team/a.git"), "bare": True, "git_dir": "a"},
            {"path": Path("/srv/elsewhere/b.git"), "bare": True, "git_dir": "b"},
        ]
        active, stores, _ = MODULE.partition_forge_stores(
            repositories, (Path("/srv/vcs/store"),)
        )
        self.assertEqual(["/srv/elsewhere/b.git"], [str(item["path"]) for item in active])
        self.assertEqual({"/srv/vcs/store": 1}, stores)

    def test_a_declared_forge_root_never_swallows_a_sibling_by_prefix(self):
        self.assertIsNone(
            MODULE.forge_store_root(Path("/srv/vcs/store-other/a.git"), (Path("/srv/vcs/store"),))
        )

    def test_repositories_that_fail_inspection_are_reported_not_crashed_on(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            broken = root / "broken"
            broken.mkdir()
            (broken / ".git").write_text("gitdir: /nowhere/that/exists\n")
            resolved, errors = MODULE.resolve_repositories([broken])
            self.assertEqual([], resolved)
            self.assertEqual(1, len(errors))
            self.assertEqual(str(broken), errors[0]["path"])
            self.assertIn("command", errors[0])


class ReadOnlyGuardTest(unittest.TestCase):
    def test_no_destructive_git_verb_is_ever_passed_to_git(self):
        arguments = git_call_arguments()
        self.assertTrue(arguments, "no git() call sites were found to check")
        destructive = set(DESTRUCTIVE_VERBS)
        self.assertEqual([], [value for _, value in arguments if value in destructive])

    def test_every_git_call_site_names_an_allowlisted_subcommand(self):
        subcommands = sorted({value for position, value in git_call_arguments() if position == 0})
        self.assertTrue(subcommands)
        self.assertEqual(set(), set(subcommands) - MODULE.READ_ONLY_GIT)

    def test_source_text_contains_no_destructive_verb_literals(self):
        offenders = [
            verb for verb in TEXT_SCAN_VERBS
            if re.search(r"""["']%s["']""" % re.escape(verb), SOURCE)
        ]
        self.assertEqual([], offenders)

    def test_the_read_only_allowlist_excludes_every_destructive_verb(self):
        self.assertEqual(set(), MODULE.READ_ONLY_GIT & set(DESTRUCTIVE_VERBS))

    def test_the_guard_refuses_destructive_subcommands(self):
        for verb in DESTRUCTIVE_VERBS:
            with self.assertRaises(RuntimeError, msg=verb):
                MODULE.assert_read_only((verb, "--anything"))

    def test_the_guard_refuses_bare_stash_because_bare_stash_removes_work(self):
        with self.assertRaises(RuntimeError):
            MODULE.assert_read_only(("stash",))
        for mutating in ("push", "pop", "apply", "drop", "clear", "save"):
            with self.assertRaises(RuntimeError):
                MODULE.assert_read_only(("stash", mutating))
        MODULE.assert_read_only(("stash", "list"))

    def test_the_guard_refuses_mutating_forms_of_allowlisted_subcommands(self):
        for args in (
            ("worktree",), ("worktree", "prune"), ("worktree", "add"),
            ("config",), ("config", "user.name", "x"),
            ("remote",), ("remote", "set-url"),
        ):
            with self.assertRaises(RuntimeError, msg=str(args)):
                MODULE.assert_read_only(args)
        MODULE.assert_read_only(("worktree", "list"))
        MODULE.assert_read_only(("config", "--get", "gc.pruneExpire"))
        MODULE.assert_read_only(("remote", "-v"))

    def test_the_guard_refuses_an_empty_invocation(self):
        with self.assertRaises(RuntimeError):
            MODULE.assert_read_only(())

    def test_git_is_invoked_from_exactly_one_guarded_choke_point(self):
        self.assertEqual(1, SOURCE.count("subprocess.run"))
        self.assertIn("assert_read_only(args)", SOURCE)
        self.assertIn("stdin=subprocess.DEVNULL", SOURCE)

    def test_no_filesystem_removal_api_is_imported_or_referenced(self):
        for banned in ("shutil", "rmtree", "os.remove", "os.unlink", "os.rmdir", ".unlink("):
            self.assertNotIn(banned, SOURCE, banned)

    def test_the_only_write_is_the_explicitly_requested_report_file(self):
        writes = re.findall(r"\.write_text\(|\.write_bytes\(|open\([^)]*['\"][wa]", SOURCE)
        self.assertEqual(1, len(writes))
        self.assertIn("destination.write_text(payload)", SOURCE)

    def test_the_report_write_refuses_to_destroy_anything(self):
        """An audit broke a real repository by overwriting .git/HEAD via
        --output. These three refusals are what stop that happening again."""
        self.assertIn('if any(part == ".git" for part in destination.parts):', SOURCE)
        self.assertIn("if destination.exists() and not args.force:", SOURCE)
        self.assertIn("if not destination.parent.is_dir():", SOURCE)
        # mkdir -p of arbitrary trees must be gone entirely.
        self.assertNotIn("mkdir(parents=True", SOURCE)

    def test_the_payload_carries_the_read_only_contract_marker(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            (root / "empty").mkdir()
            report = MODULE.scan([root], max_depth=2, caches_root=root / "no-such-cache")
            self.assertTrue(report["read_only"])
            self.assertEqual(1, report["schema_version"])
            self.assertEqual([], report["findings"])
            self.assertTrue(any("fsck" in warning for warning in report["warnings"]))
            self.assertTrue(any("Vendor trees" in warning for warning in report["warnings"]))


class ReportTest(unittest.TestCase):
    def test_reports_a_dirty_unmirrored_repository_at_full_severity(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            repo = root / "app"
            repo.mkdir()
            run_git(repo, "init", "-q", "-b", "main")
            (repo / "tracked.md").write_text("tracked\n")
            run_git(repo, "add", "tracked.md")
            run_git(repo, "commit", "-qm", "first")
            (repo / "loose.md").write_text("never committed\n")
            shelf = repo / ".idea" / "shelf" / "Uncommitted_[Changes]"
            shelf.mkdir(parents=True)
            (shelf / "shelved.patch").write_text("--- a/tracked.md\n+++ b/tracked.md\n")

            report = MODULE.scan([root], max_depth=3, jobs=2, caches_root=root / "absent")
            vectors = {item["vector"]: item for item in report["findings"]}
            self.assertEqual("CRITICAL", vectors["V1"]["severity"])
            self.assertEqual("CRITICAL", vectors["V5"]["severity"])
            self.assertEqual("HIGH", vectors["V7"]["severity"])
            self.assertIn("loose.md", vectors["V5"]["evidence"])
            self.assertIn("no remote configured", vectors["V7"]["evidence"])
            self.assertEqual(1, report["repositories_inspected"])
            for item in report["findings"]:
                self.assertTrue(item["next_step"])
                self.assertIn(item["severity"], MODULE.SEVERITY_RANK)

    def test_text_render_groups_by_severity_and_states_the_read_only_contract(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            (root / "empty").mkdir()
            text = MODULE.render_text(MODULE.scan([root], max_depth=2, caches_root=root / "absent"))
            self.assertIn("warrior scan", text)
            self.assertIn("Read-only report.", text)
            self.assertIn("Moof", text)  # attribution to the origin project is kept
            self.assertTrue(text.endswith("\n"))


class PortabilityTest(unittest.TestCase):
    """The port must carry nothing from the machine it was written on."""

    def test_no_developer_specific_path_is_baked_into_the_tool(self):
        for offender in ("/Users/", "/home/", "deanhowe", "PROJECTS", "moof.local", "kiro"):
            self.assertNotIn(offender, SOURCE, offender)

    def test_the_origin_project_is_still_credited(self):
        self.assertIn("Moof", SOURCE)

    def test_jetbrains_caches_are_discovered_not_assumed(self):
        roots = MODULE.jetbrains_cache_roots()
        self.assertTrue(roots)
        self.assertEqual({"JetBrains"}, {root.name for root in roots})
        self.assertTrue(all(root.is_absolute() for root in roots))
        home = Path.home()
        if sys.platform == "darwin":
            self.assertEqual(home / "Library" / "Caches" / "JetBrains", roots[0])
        elif os.name != "nt":
            self.assertIn(home / ".cache" / "JetBrains", roots)

    def test_the_platform_default_can_be_overridden_from_the_environment(self):
        with tempfile.TemporaryDirectory() as temporary:
            first = Path(temporary) / "one"
            second = Path(temporary) / "two"
            override = os.pathsep.join([str(first), str(second)])
            with unittest.mock.patch.dict(
                os.environ, {MODULE.JETBRAINS_CACHES_ENV: override}, clear=False
            ):
                self.assertEqual([first, second], MODULE.jetbrains_cache_roots())

    def test_a_missing_jetbrains_cache_is_a_stated_boundary_not_a_crash(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            (root / "empty").mkdir()
            report = MODULE.scan([root], max_depth=2, caches_root=root / "no-such-cache")
            self.assertEqual([], report["scan_policy"]["jetbrains_cache_roots_present"])
            self.assertTrue(any("No JetBrains cache" in item for item in report["warnings"]))

    def test_a_tree_with_no_git_anywhere_scans_clean(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            (root / "docs" / "deep").mkdir(parents=True)
            (root / "docs" / "deep" / "notes.md").write_text("no git here\n")
            report = MODULE.scan([root], max_depth=4, caches_root=root / "absent")
            self.assertEqual(0, report["repositories_discovered"])
            self.assertEqual([], report["findings"])
            self.assertEqual([], report["errors"])
            self.assertTrue(report["read_only"])

    def test_roots_come_from_the_caller_and_are_recorded_verbatim(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            report = MODULE.scan([root], max_depth=1, caches_root=root / "absent")
            self.assertEqual([str(root)], report["roots"])


if __name__ == "__main__":
    unittest.main()
