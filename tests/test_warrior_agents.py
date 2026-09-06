"""Deterministic parity and preservation tests for Warrior agent profiles."""

from __future__ import annotations

import importlib.machinery
import importlib.util
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).parents[1] / "bin" / "warrior-agents"
LOADER = importlib.machinery.SourceFileLoader("warrior_agents", str(SCRIPT))
SPEC = importlib.util.spec_from_loader(LOADER.name, LOADER)
MODULE = importlib.util.module_from_spec(SPEC)
LOADER.exec_module(MODULE)


class AgentProfileTests(unittest.TestCase):
    def test_every_native_projection_satisfies_its_role_contract(self):
        for harness in MODULE.HARNESSES:
            for role in MODULE.ROLES:
                with self.subTest(harness=harness, role=role):
                    self.assertEqual([], MODULE.validate_source(harness, role))

    def test_install_is_plan_only_until_apply_and_never_overwrites(self):
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            target = MODULE.destination_path("copilot", "guardian", project)
            self.assertEqual(0, MODULE.command_install("copilot", "guardian", project, False))
            self.assertFalse(target.exists())
            self.assertEqual(0, MODULE.command_install("copilot", "guardian", project, True))
            self.assertTrue(target.is_file())
            target.write_text("developer-owned\n")
            self.assertEqual(2, MODULE.command_install("copilot", "guardian", project, True))
            self.assertEqual("developer-owned\n", target.read_text())

    def test_builder_is_locked_in_every_harness(self):
        kiro = MODULE.source_path("kiro", "builder").read_text()
        claude = MODULE.source_path("claude", "builder").read_text()
        copilot = MODULE.source_path("copilot", "builder").read_text()
        codex = MODULE.source_path("codex", "builder").read_text()
        self.assertIn('"requireApproval": "always"', kiro)
        self.assertIn("Refuse", claude)
        self.assertIn("disable-model-invocation: true", copilot)
        self.assertIn("exact file allow-list", codex)

    def test_codex_uses_native_toml_agent_destination(self):
        self.assertEqual(".toml", MODULE.source_path("codex", "guardian").suffix)
        self.assertEqual(
            Path(".codex/agents/warrior-guardian.toml"),
            MODULE.destination_path("codex", "guardian", Path("/project")).relative_to("/project"),
        )

    def test_wayfinder_requires_evidence_for_identity_quotes_and_handoff(self):
        for harness in MODULE.HARNESSES:
            profile = MODULE.source_path(harness, "wayfinder").read_text().lower()
            with self.subTest(harness=harness):
                self.assertIn("authoritative runtime metadata", profile)
                self.assertIn("exact observed source text", profile)
                self.assertIn("deterministic validation", profile)


if __name__ == "__main__":
    unittest.main()
