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
