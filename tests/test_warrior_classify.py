from __future__ import annotations

import importlib.machinery
import importlib.util
import sqlite3
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "bin" / "warrior-classify"
LOADER = importlib.machinery.SourceFileLoader("warrior_classify", str(SCRIPT))
SPEC = importlib.util.spec_from_loader(LOADER.name, LOADER)
MODULE = importlib.util.module_from_spec(SPEC)
LOADER.exec_module(MODULE)


class SettingsFixture(dict):
    source = "fixture"


class IdentityDatabaseContractTest(unittest.TestCase):
    def test_custom_identity_database_requires_its_query_instead_of_assuming_a_private_schema(self):
        with tempfile.TemporaryDirectory() as temporary:
            database = Path(temporary) / "identity.sqlite"
            connection = sqlite3.connect(database)
            connection.execute("CREATE TABLE identities(path TEXT, status TEXT)")
            connection.close()
            settings = SettingsFixture(identity_db=str(database))

            with self.assertRaisesRegex(MODULE.ConfigError, "explicit identity_query"):
                MODULE.identity_index(settings, None, None)

    def test_explicit_identity_query_is_portable(self):
        with tempfile.TemporaryDirectory() as temporary:
            database = Path(temporary) / "identity.sqlite"
            connection = sqlite3.connect(database)
            connection.execute("CREATE TABLE identities(path TEXT, status TEXT)")
            connection.execute("INSERT INTO identities VALUES ('project-one', 'owned')")
            connection.commit()
            connection.close()
            settings = SettingsFixture(
                identity_db=str(database),
                identity_query="SELECT path, status FROM identities",
            )

            self.assertEqual(
                MODULE.identity_index(settings, None, None),
                {"project-one": "owned"},
            )


if __name__ == "__main__":
    unittest.main()
