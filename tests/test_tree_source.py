"""Authored tree source and its generated artifact must agree."""

from __future__ import annotations

import json
import os
import sys
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "package", "vyoscli", "files", "usr", "lib"))

from vyoscli.config_tree import TREE  # noqa: E402


class TreeSourceTest(unittest.TestCase):
    def test_generated_tree_matches_schema_source(self):
        with open(os.path.join(REPO, "schema", "config-tree.json"),
                  encoding="utf-8") as f:
            source = json.load(f)
        self.assertEqual(TREE, source,
                         "config_tree.py is stale; run "
                         "python3 scripts/build-config-tree.py")

    def test_node_names_are_unique_per_parent(self):
        def walk(items):
            names = set()
            for item in items:
                self.assertIsInstance(item.get("name"), str)
                self.assertTrue(item["name"])
                self.assertNotIn(item["name"], names, item["name"])
                names.add(item["name"])
                walk(item.get("children") or [])

        walk(TREE)

    def test_dynamic_nodes_have_templates(self):
        def walk(items):
            for item in items:
                if item.get("dyn"):
                    self.assertIn("tpl_help", item)
                walk(item.get("children") or [])

        walk(TREE)


if __name__ == "__main__":
    unittest.main()
