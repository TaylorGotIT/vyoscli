"""show interface should list configured + physical ports, not kernel noise."""

from __future__ import annotations

import os
import sys
import types
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from vyoscli import op_show  # noqa: E402


class _Store:
    def get(self, path, candidate=False):
        if path == ["interfaces"]:
            return {
                "ethernet": {"eth0": {"description": "WAN"}},
                "tunnel": {"tun10": {"description": "GRE"}},
                "dummy": {},
            }
        return None


LINK = """\
1: lo: <LOOPBACK,UP> mtu 65536 state UNKNOWN
2: eth0: <BROADCAST,UP> mtu 1500 state UP link/ether aa:bb:cc:dd:ee:ff
3: gre0@NONE: <NOARP> mtu 1476 state DOWN
4: gretap0@NONE: <BROADCAST> mtu 1462 state DOWN
5: dummy0: <BROADCAST> mtu 1500 state DOWN link/ether 00:11:22:33:44:55
6: tunl0@NONE: <NOARP> mtu 1480 state DOWN
7: br-lan: <BROADCAST,UP> mtu 1500 state UP link/ether 66:77:88:99:aa:bb
"""

ADDR = """\
2: eth0    inet 192.0.2.10/24 brd 192.0.2.255 scope global eth0
7: br-lan  inet 192.168.1.1/24 brd 192.168.1.255 scope global br-lan
"""


class ShowArpTest(unittest.TestCase):
    def test_formats_ip_neigh_as_vyos_table(self):
        def fake_run(args, **kwargs):
            return types.SimpleNamespace(stdout=(
                "192.168.75.241 dev eth1 lladdr 94:d2:bc:5d:e6:0c REACHABLE\n"
                "192.168.75.244 dev eth1 lladdr 2c:f0:5d:3c:0a:41 STALE\n"
                "fe80::1 dev eth1 lladdr aa:bb:cc:dd:ee:ff router REACHABLE\n"))
        with mock.patch("subprocess.run", side_effect=fake_run):
            text = op_show._op_show_arp(None, "")
        self.assertIn("Address", text)
        self.assertIn("HWaddress", text)
        self.assertIn("192.168.75.241", text)
        self.assertIn("94:d2:bc:5d:e6:0c", text)
        self.assertIn("eth1", text)
        self.assertNotIn("fe80", text)


class PagerTest(unittest.TestCase):
    def test_non_tty_prints_everything(self):
        import io
        from contextlib import redirect_stdout
        from harness import new_cli
        cli = new_cli()
        buf = io.StringIO()
        with redirect_stdout(buf):
            cli._print_output("one\ntwo\nthree")
        self.assertIn("one", buf.getvalue())
        self.assertIn("three", buf.getvalue())


class ShowInterfaceTest(unittest.TestCase):
    def test_lists_configured_and_physical_only(self):
        def fake_run(args, **kwargs):
            out = LINK if args[-1] == "link" else ADDR
            return types.SimpleNamespace(stdout=out)

        ctx = types.SimpleNamespace(store=_Store())
        with mock.patch("subprocess.run", side_effect=fake_run):
            text = op_show._op_show_interfaces(ctx, "")
        self.assertIn("tun10", text)
        self.assertIn("GRE", text)
        self.assertIn("eth0", text)
        self.assertIn("192.0.2.10/24", text)
        self.assertIn("br-lan", text)
        self.assertIn("S/L", text)
        self.assertIn("IP Address", text)
        self.assertNotIn("MAC", text)
        self.assertNotIn("gre0", text)
        self.assertNotIn("gretap0", text)
        self.assertNotIn("dummy0", text)
        self.assertNotIn("tunl0", text)
        self.assertNotIn("@NONE", text)


if __name__ == "__main__":
    unittest.main()
