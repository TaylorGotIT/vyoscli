"""Backend tests: what a commit actually drives on the box.

``uci``/``ip``/``init.d`` are replaced by a recorder, so the assertions are
about the exact argv sequence vyoscli would run on an OpenWrt device —
runnable on any OS without a router.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from harness import cfg, load_json, new_cli  # noqa: E402

from vyoscli import config as config_mod  # noqa: E402


class FakeSystem:
    """Records every subprocess call; fakes `uci show` output."""

    def __init__(self, uci_show: str = ""):
        self.calls: list[list[str]] = []
        self.uci_show = uci_show

    def run(self, cmd, *args, **kwargs):
        cmd = [str(c) for c in cmd]
        self.calls.append(cmd)
        out = self.uci_show if cmd[:2] == ["uci", "show"] else ""
        return subprocess.CompletedProcess(cmd, 0, stdout=out, stderr="")

    def uci_calls(self):
        return [c for c in self.calls if c and c[0] == "uci"]

    def uci_statements(self):
        """uci calls minus the 'show'/'commit'/'apply' noise."""
        return [c for c in self.uci_calls()
                if len(c) > 1 and c[1] in ("set", "add_list", "delete")]


class CrontabMergeTest(unittest.TestCase):
    """Pure function: managed blocks must disappear with their job line."""

    def test_removing_a_job_removes_its_cron_line(self):
        existing = (
            "0 1 * * * /usr/bin/user-job\n"
            "# --- vyoscli:begin:backup ---\n"
            "0 3 * * * /bin/true\n"
            "# --- vyoscli:end:backup ---\n"
        )
        lines = config_mod.ConfigStore.merge_crontab(existing, {})
        self.assertIn("0 1 * * * /usr/bin/user-job", lines)
        self.assertNotIn("0 3 * * * /bin/true", lines)
        self.assertFalse(any("vyoscli:" in ln for ln in lines))

    def test_keeps_user_lines_and_rewrites_block(self):
        existing = "0 1 * * * /usr/bin/user-job\n# --- vyoscli:begin:x ---\n# old\n*/9 * * * * /bin/false\n# --- vyoscli:end:x ---\n"
        jobs = {"y": {"schedule": "*/5 * * * *", "script": "/bin/true",
                      "description": "test"}}
        lines = config_mod.ConfigStore.merge_crontab(existing, jobs)
        self.assertIn("0 1 * * * /usr/bin/user-job", lines)
        self.assertIn("*/5 * * * * /bin/true", lines)
        self.assertIn("# test", lines)
        self.assertNotIn("*/9 * * * * /bin/false", lines)


class CommitBackendTest(unittest.TestCase):
    def setUp(self):
        self.cli = new_cli()
        self.fake = FakeSystem()
        self._patches = [
            mock.patch.object(config_mod.subprocess, "run", self.fake.run),
            mock.patch.object(config_mod.shutil, "which",
                              lambda name: f"/sbin/{name}" if name == "uci" else None),
        ]
        for p in self._patches:
            p.start()

    def tearDown(self):
        for p in self._patches:
            p.stop()

    def commit(self):
        return self.cli.store.commit()

    def test_hostname_goes_through_uci(self):
        cfg(self.cli, "set system host-name edge-1")
        out = self.commit()
        self.assertIn("Commit complete", out)
        self.assertIn(["uci", "set", "system.@system[0].hostname=edge-1"],
                      self.fake.uci_calls())
        self.assertIn(["uci", "commit", "system"], self.fake.uci_calls())

    def test_ethernet_address_uses_netifd_section(self):
        cfg(self.cli, "set interfaces ethernet eth0 address 203.0.113.10/24")
        self.commit()
        calls = self.fake.uci_calls()
        self.assertIn(["uci", "set", "network.vyos_eth0=interface"], calls)
        self.assertIn(["uci", "set", "network.vyos_eth0.ifname=eth0"], calls)
        self.assertIn(["uci", "add_list", "network.vyos_eth0.ipaddr=203.0.113.10/24"],
                      calls)
        self.assertTrue(any(c[:2] == ["uci", "commit"] for c in calls))

    def test_reuses_existing_uci_section(self):
        self.fake.uci_show = "network.@interface[0].ifname='eth0'\n"
        cfg(self.cli, "set interfaces ethernet eth0 address 203.0.113.11/24")
        self.commit()
        calls = self.fake.uci_calls()
        self.assertNotIn(["uci", "set", "network.vyos_eth0=interface"], calls)
        self.assertIn(["uci", "set", "network.@interface[0].ifname=eth0"], calls)

    def test_static_route_creates_marked_section(self):
        cfg(self.cli, "set protocols static route 10.9.0.0/16 next-hop 192.168.1.254")
        self.commit()
        calls = self.fake.uci_calls()
        self.assertIn(["uci", "set", "network.vyos_route_10_9_0_0_16=route"], calls)
        self.assertIn(["uci", "set", "network.vyos_route_10_9_0_0_16.target=10.9.0.0/16"],
                      calls)
        self.assertIn(["uci", "set", "network.vyos_route_10_9_0_0_16.gateway=192.168.1.254"],
                      calls)

    def test_ssh_port_goes_through_dropbear(self):
        cfg(self.cli, "set service ssh port 2222")
        self.commit()
        self.assertIn(["uci", "set", "dropbear.@dropbear[0].Port=2222"],
                      self.fake.uci_calls())

    def test_firewall_zone_and_rule_are_applied(self):
        cfg(self.cli,
            "set firewall zone lan network lan",
            "set firewall rule 100 dest-port 22",
            "set firewall rule 100 target ACCEPT")
        self.commit()
        calls = self.fake.uci_calls()
        self.assertIn(["uci", "set", "firewall.vyos_zone_lan=zone"], calls)
        self.assertIn(["uci", "set", "firewall.vyos_zone_lan.name=lan"], calls)
        self.assertIn(["uci", "set", "firewall.vyos_rule_100=rule"], calls)
        self.assertIn(["uci", "set", "firewall.vyos_rule_100.target=ACCEPT"], calls)

    def test_dhcp_subnet_maps_to_uci(self):
        cfg(self.cli,
            "set interfaces ethernet eth1 address 192.168.50.1/24",
            "set service dhcp-server shared-network-name LAN subnet 192.168.50.0/24 "
            "default-router 192.168.50.1",
            "set service dhcp-server shared-network-name LAN subnet 192.168.50.0/24 "
            "range 0 start 192.168.50.100",
            "set service dhcp-server shared-network-name LAN subnet 192.168.50.0/24 "
            "range 0 stop 192.168.50.200")
        out = self.commit()
        self.assertIn("dhcp LAN/192.168.50.0/24 -> eth1", out)
        calls = self.fake.uci_calls()
        sec = "dhcp.vyos_dhcp_LAN_192_168_50_0_24"
        self.assertIn(["uci", "set", f"{sec}=dhcp"], calls)
        self.assertIn(["uci", "set", f"{sec}.interface=eth1"], calls)
        self.assertIn(["uci", "set", f"{sec}.start=100"], calls)
        self.assertIn(["uci", "set", f"{sec}.limit=101"], calls)
        self.assertIn(["uci", "add_list", f"{sec}.dhcp_option=router,192.168.50.1"],
                      calls)

    def test_dhcp_without_matching_interface_is_reported(self):
        cfg(self.cli,
            "set service dhcp-server shared-network-name GUEST subnet 10.77.0.0/24 "
            "default-router 10.77.0.1")
        out = self.commit()
        self.assertIn("no interface holds an address", out)
        self.assertNotIn(["uci", "set", "dhcp.vyos_dhcp_GUEST_10_77_0_0_24=dhcp"],
                         self.fake.uci_calls())

    def test_legacy_scalar_ntp_is_not_split_into_characters(self):
        # Old running.json stored a single server as a string; applying it must
        # still produce one add_list, not one per character.
        old = {"system": {}}
        new = {"system": {"ntp": "223.5.5.5"}}
        self.cli.store._apply_system_meta(old, new)
        server_calls = [c for c in self.fake.uci_calls()
                        if c[:2] == ["uci", "add_list"]
                        and c[2].startswith("system.ntp.server=")]
        self.assertEqual(server_calls,
                         [["uci", "add_list", "system.ntp.server=223.5.5.5"]])

    def test_refuses_to_duplicate_a_device_used_by_lan_or_wan(self):
        # eth1 is already bound to network.wan (proto dhcp). Applying a VyOS
        # address must not create a second interface on the same device.
        self.fake.uci_show = "network.wan.device='eth1'\n"
        cfg(self.cli, "set interfaces ethernet eth1 address 192.168.1.2/24")
        out = self.commit()
        self.assertIn("already used by network.wan", out)
        calls = self.fake.uci_calls()
        self.assertNotIn(["uci", "set", "network.vyos_eth1=interface"], calls)
        self.assertNotIn(["uci", "set", "network.wan.ipaddr=192.168.1.2/24"], calls)

    def test_dnat_uses_rule_level_ids_and_fw4_options(self):
        cfg(self.cli,
            "set nat destination rule 10 port 65001",
            "set nat destination rule 10 to 192.0.2.9")
        self.commit()
        calls = self.fake.uci_calls()
        self.assertIn(["uci", "set", "firewall.vyos_nat_dst_10=redirect"], calls)
        self.assertIn(["uci", "set", "firewall.vyos_nat_dst_10.src_dport=65001"], calls)
        self.assertIn(["uci", "set", "firewall.vyos_nat_dst_10.dest_ip=192.0.2.9"], calls)
        self.assertNotIn(["uci", "set", "firewall.vyos_nat_dst_rule=redirect"], calls)

    def test_snat_maps_rule_id(self):
        cfg(self.cli, "set nat source rule 100 out-interface wan")
        self.commit()
        calls = self.fake.uci_calls()
        self.assertIn(["uci", "set", "firewall.vyos_nat_src_100=nat"], calls)
        self.assertIn(["uci", "set", "firewall.vyos_nat_src_100.dest=wan"], calls)
        self.assertNotIn(["uci", "set", "firewall.vyos_nat_src_rule=nat"], calls)

    def test_empty_nat_rule_dict_creates_no_section(self):
        cfg(self.cli, "set nat destination rule 10 port 65001")
        self.commit()
        cfg(self.cli, "delete nat destination rule 10")
        self.commit()          # JSON keeps nat.destination.rule = {}
        self.assertNotIn(["uci", "set", "firewall.vyos_nat_dst_rule=redirect"],
                         self.fake.uci_calls())

    def test_bridge_uses_device_section(self):
        # `type bridge` on an *interface* makes netifd create "br-<name>",
        # which overflows IFNAMSIZ (br-vyos_br_br100 = 18 chars).
        cfg(self.cli,
            "set interfaces bridge br9 member eth2",
            "set interfaces bridge br9 address 192.0.2.2/24")
        self.commit()
        calls = self.fake.uci_calls()
        self.assertIn(["uci", "set", "network.br9_dev=device"], calls)
        self.assertIn(["uci", "set", "network.br9_dev.type=bridge"], calls)
        self.assertIn(["uci", "set", "network.br9_dev.name=br9"], calls)
        self.assertIn(["uci", "add_list", "network.br9_dev.ports=eth2"], calls)
        self.assertIn(["uci", "set", "network.vyos_br_br9.device=br9"], calls)
        self.assertNotIn(["uci", "set", "network.vyos_br_br9.type=bridge"], calls)

        cfg(self.cli, "delete interfaces bridge br9")
        self.commit()
        self.assertIn(["ip", "link", "del", "br9"], self.fake.calls)
        self.assertIn(["uci", "delete", "network.br9_dev"], self.fake.calls)

    def test_dummy_gets_a_device_section(self):
        cfg(self.cli, "set interfaces dummy dum9 address 192.0.2.1/32")
        self.commit()
        calls = self.fake.uci_calls()
        self.assertIn(["uci", "set", "network.dum9_dev=device"], calls)
        self.assertIn(["uci", "set", "network.dum9_dev.type=dummy"], calls)
        self.assertIn(["uci", "set", "network.dum9.device=dum9"], calls)
        self.assertIn(["uci", "add_list", "network.dum9.ipaddr=192.0.2.1/32"], calls)

    def test_removed_dummy_sections_are_deleted(self):
        cfg(self.cli, "set interfaces dummy dum9 address 192.0.2.1/32")
        self.commit()
        cfg(self.cli, "delete interfaces dummy dum9")
        self.commit()
        calls = self.fake.uci_calls()
        self.assertIn(["uci", "delete", "network.dum9"], calls)
        self.assertIn(["uci", "delete", "network.dum9_dev"], calls)

    def test_no_backend_when_uci_missing(self):
        with mock.patch.object(config_mod.shutil, "which", lambda name: None):
            cfg(self.cli, "set system host-name offline")
            out = self.commit()
        self.assertIn("no uci on this host", out)
        self.assertEqual(load_json(self.cli.store.running_path)["system"]["host-name"],
                         "offline")

    def test_running_json_written_only_after_apply(self):
        seen = {}
        real_run = self.fake.run

        def spy(cmd, *args, **kwargs):
            if "running.json" not in seen and cmd[0] == "uci" and cmd[1] == "set":
                with open(self.cli.store.running_path, encoding="utf-8") as f:
                    seen["running.json"] = json.load(f)["system"]["host-name"]
            return real_run(cmd, *args, **kwargs)

        with mock.patch.object(config_mod.subprocess, "run", spy):
            cfg(self.cli, "set system host-name late-write")
            self.commit()
        # The first uci write must still observe the *old* running config.
        self.assertEqual(seen.get("running.json"), "OpenWrt")


if __name__ == "__main__":
    unittest.main(verbosity=2)
