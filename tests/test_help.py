"""VyOS-style help hints and completion."""

from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from harness import new_cli  # noqa: E402


class HelpTest(unittest.TestCase):
    def setUp(self):
        self.cli = new_cli()
        self.cli.ctx.mode = "cfg"

    def test_value_hint_uses_vyos_placeholder(self):
        text = self.cli._help_text("set interfaces ethernet eth0 address ")
        self.assertIn("<x.x.x.x/xx>", text)
        self.assertIn("IPv4 address/prefix", text)
        self.assertNotIn(" value", text)

    def test_dynamic_placeholder_has_context(self):
        text = self.cli._help_text("set interfaces bridge ")
        self.assertIn("<br-name>", text)

    def test_ping_tcp_completion_has_ip_port(self):
        self.cli.ctx.mode = "op"
        pairs = dict(self.cli._matches_with_help(["ping", "tcp", ""]))
        self.assertEqual(pairs.get("ip"), "IP address")
        self.assertEqual(pairs.get("port"), "Port number")

    def test_completion_attribute_lists_ifnames(self):
        self.cli.ctx.mode = "op"
        node = (self.cli.tree.op_root.children["show"].children["interfaces"]
                .children["ethernet"])
        node._completion = lambda: ["eth0", "eth1"]
        pairs = self.cli._matches_with_help(
            ["show", "interfaces", "ethernet", ""])
        names = [name for name, _ in pairs]
        self.assertIn("eth0", names)
        self.assertIn("eth1", names)
        self.assertNotIn("<text>", names)


if __name__ == "__main__":
    unittest.main()
