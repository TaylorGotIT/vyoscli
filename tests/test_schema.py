"""Schema coverage: every declarative spec must resolve and store a value."""

from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from harness import cfg_errors, new_cli  # noqa: E402

from vyoscli import schema  # noqa: E402
from vyoscli.tree import coerce_value  # noqa: E402

SAMPLE = {
    "host": "edge-1",
    "ipv4": "1.2.3.4",
    "ipv4net": "10.0.0.1/24",
    "int": "9000",
    "bool": "true",
    "str": "sample",
    "port": "2222",
}


class SchemaTest(unittest.TestCase):
    def setUp(self):
        self.cli = new_cli()

    def test_no_duplicate_paths(self):
        for name, group in schema.GROUPS.items():
            paths = [spec.path for spec in group]
            self.assertEqual(len(paths), len(set(paths)), name)

    def test_every_system_spec_resolves(self):
        for spec in schema.SYSTEM:
            with self.subTest(path=spec.path):
                value = SAMPLE[spec.type]
                errs = cfg_errors(self.cli,
                                  f"set system {spec.path} {value}")
                self.assertEqual(errs, [], spec.path)
                stored = self.cli.store.get(["system"] + spec.path.split())
                if isinstance(stored, list):
                    self.assertIn(value, stored)
                else:
                    self.assertEqual(stored, value)

    def test_every_ethernet_spec_resolves(self):
        for spec in schema.ETHERNET:
            with self.subTest(path=spec.path):
                raw = SAMPLE[spec.type]
                expected = coerce_value(spec.type, raw)
                errs = cfg_errors(
                    self.cli, f"set interfaces ethernet eth0 {spec.path} {raw}")
                self.assertEqual(errs, [], spec.path)
                path = ["interfaces", "ethernet", "eth0"] + spec.path.split()
                stored = self.cli.store.get(path)
                if isinstance(stored, list):
                    self.assertIn(expected, stored)
                else:
                    self.assertEqual(stored, expected)

    def test_repeatable_specs_match_default_lists(self):
        from vyoscli.config import DEFAULT_RUNNING
        for spec in schema.SYSTEM:
            if not spec.repeatable:
                continue
            cur = DEFAULT_RUNNING
            for part in ["system"] + spec.path.split():
                cur = cur[part]
            with self.subTest(path=spec.path):
                self.assertIsInstance(cur, list)


if __name__ == "__main__":
    unittest.main(verbosity=2)
