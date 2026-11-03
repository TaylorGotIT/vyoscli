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

    def __init__(self, uci_show: str = "", get_values=None):
        self.calls: list[list[str]] = []
        self.uci_show = uci_show
        self.get_values = get_values or {}

    def run(self, cmd, *args, **kwargs):
        cmd = [str(c) for c in cmd]
        self.calls.append(cmd)
        if cmd[:3] == ["uci", "-q", "get"] and len(cmd) == 4:
            key = cmd[3]
            rc = 0 if key in self.get_values else 1
            return subprocess.CompletedProcess(cmd, rc,
                                               stdout=self.get_values.get(key, ""),
                                               stderr="")
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


class FrrRenderTest(unittest.TestCase):
    def test_render_bgp_and_policy(self):
        lines = config_mod.ConfigStore.render_frr_conf(
            {"local-as": 65001, "router-id": "10.0.0.1",
             "neighbor": {"10.0.0.2": {"remote-as": 65002,
                                       "description": "peer"}},
             "network": ["10.9.0.0/16"]},
            {"RM1": {"permit": {"10": {"set": {"local-preference": 200}}}}},
            {"10": {"10": {"regex": "65001:*", "action": "permit"}}},
            "r1")
        text = "\n".join(lines)
        for needle in ("router bgp 65001", "bgp router-id 10.0.0.1",
                       "neighbor 10.0.0.2 remote-as 65002",
                       "neighbor 10.0.0.2 description peer",
                       "network 10.9.0.0/16",
                       "route-map RM1 permit 10",
                       "set local-preference 200",
                       "bgp community-list expanded 10 permit 65001:*"):
            self.assertIn(needle, text)

    def test_disabled_bgp_has_no_router_block(self):
        text = "\n".join(config_mod.ConfigStore.render_frr_conf({}, {}, {}, "r1"))
        self.assertNotIn("router bgp", text)


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
        self.assertIn(["/etc/init.d/system", "reload"], self.fake.calls)
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

    def test_refuses_to_replace_a_dynamic_proto(self):
        # eth1 is the DHCP WAN: applying a VyOS static address must not
        # silently replace the DHCP setup, nor create a duplicate interface.
        self.fake.uci_show = ("network.wan=interface\n"
                              "network.wan.device='eth1'\n"
                              "network.wan.proto='dhcp'\n")
        cfg(self.cli, "set interfaces ethernet eth1 address 192.168.1.2/24")
        out = self.commit()
        self.assertIn("refusing to replace it", out)
        calls = self.fake.uci_calls()
        self.assertNotIn(["uci", "set", "network.vyos_eth1=interface"], calls)
        self.assertNotIn(["uci", "set", "network.wan.proto=static"], calls)

    def test_takeover_backs_up_and_restores_section(self):
        self.fake.uci_show = ("network.wan=interface\n"
                              "network.wan.device='eth5'\n"
                              "network.wan.proto='static'\n")
        self.fake.get_values = {"network.wan.proto": "static",
                                "network.wan.device": "eth5",
                                "network.wan.ipaddr": "192.0.2.1/24",
                                "network.vyos_eth5": "interface"}
        cfg(self.cli, "set interfaces ethernet eth5 address 192.0.2.5/24")
        self.commit()
        backup = os.path.join(self.cli.store.base_dir, "backup", "network.wan.json")
        self.assertTrue(os.path.exists(backup))
        cfg(self.cli, "delete interfaces ethernet eth5 address 192.0.2.5/24")
        self.commit()
        self.assertFalse(os.path.exists(backup))
        calls = self.fake.uci_calls()
        self.assertIn(["uci", "set", "network.wan.proto=static"], calls)
        self.assertIn(["uci", "add_list", "network.wan.ipaddr=192.0.2.1/24"], calls)

    def test_removing_address_drops_vyos_interface(self):
        cfg(self.cli, "set interfaces ethernet eth5 address 192.0.2.6/24")
        self.commit()
        self.fake.get_values = {"network.vyos_eth5": "interface"}
        cfg(self.cli, "delete interfaces ethernet eth5 address 192.0.2.6/24")
        self.commit()
        self.assertIn(["uci", "delete", "network.vyos_eth5"], self.fake.calls)

    def test_takes_over_a_static_interface_on_the_same_device(self):
        self.fake.uci_show = ("network.wan=interface\n"
                              "network.wan.device='eth1'\n"
                              "network.wan.proto='static'\n")
        cfg(self.cli, "set interfaces ethernet eth1 address 192.0.2.5/24")
        out = self.commit()
        self.assertIn("applied to existing network.wan", out)
        calls = self.fake.uci_calls()
        self.assertIn(["uci", "add_list", "network.wan.ipaddr=192.0.2.5/24"], calls)
        self.assertNotIn(["uci", "set", "network.vyos_eth1=interface"], calls)

    def test_refuses_bridge_ports(self):
        self.fake.uci_show = ("network.lan=interface\n"
                              "network.lan.device='br-lan'\n"
                              "network.lan.proto='static'\n"
                              "network.@device[0]=device\n"
                              "network.@device[0].type='bridge'\n"
                              "network.@device[0].name='br-lan'\n"
                              "network.@device[0].ports='eth0'\n")
        cfg(self.cli, "set interfaces ethernet eth0 address 192.0.2.6/24")
        out = self.commit()
        self.assertIn("is a port of network.lan", out)
        self.assertNotIn(["uci", "set", "network.vyos_eth0=interface"],
                         self.fake.uci_calls())

    def test_wireguard_peer_endpoint_split_and_cleanup(self):
        key = "A" * 43 + "="
        cfg(self.cli,
            f"set interfaces wireguard wg9 private-key {key}",
            "set interfaces wireguard wg9 address 10.99.0.1/24",
            "set interfaces wireguard wg9 peer PUBKEY allowed-ips 10.99.0.2/32",
            "set interfaces wireguard wg9 peer PUBKEY endpoint 192.0.2.10:51999")
        self.commit()
        calls = self.fake.uci_calls()
        self.assertIn(["uci", "set", "network.wg9.proto=wireguard"], calls)
        self.assertIn(["uci", "set",
                       "network.peer_wg9_PUBKEY.endpoint_host=192.0.2.10"], calls)
        self.assertIn(["uci", "set",
                       "network.peer_wg9_PUBKEY.endpoint_port=51999"], calls)
        cfg(self.cli, "delete interfaces wireguard wg9")
        self.commit()
        self.assertIn(["uci", "delete", "network.wg9"], self.fake.calls)
        self.assertIn(["ip", "link", "del", "wg9"], self.fake.calls)

    def test_dnat_renders_to_nft(self):
        cfg(self.cli,
            "set nat destination rule 10 protocol tcp",
            "set nat destination rule 10 destination port 8080",
            "set nat destination rule 10 translation address 192.168.1.10",
            "set nat destination rule 10 translation port 80",
            "set nat destination rule 10 hairpin true")
        self.commit()
        path = os.path.join(self.cli.store.base_dir, "nat.nft")
        text = open(path, encoding="utf-8").read()
        self.assertIn("table inet vyos_nat", text)
        self.assertIn("tcp dport 8080", text)
        self.assertIn("dnat to 192.168.1.10:80", text)
        self.assertEqual(text.count("dnat to"), 2)   # + hairpin copy
        self.assertIn(["nft", "-f", path], self.fake.calls)

    def test_snat_masquerade_renders_to_nft(self):
        cfg(self.cli,
            "set nat source rule 100 out-interface eth1",
            "set nat source rule 100 source address 192.168.0.0/16",
            "set nat source rule 100 translation address masquerade")
        self.commit()
        text = open(os.path.join(self.cli.store.base_dir, "nat.nft"),
                    encoding="utf-8").read()
        self.assertIn("oifname \"eth1\"", text)
        self.assertIn("192.168.0.0/16", text)
        self.assertIn("masquerade", text)

    def test_removing_nat_deletes_table(self):
        cfg(self.cli, "set nat source rule 100 translation address masquerade")
        self.commit()
        cfg(self.cli, "delete nat source rule 100")
        self.commit()
        self.assertIn(["nft", "delete", "table", "inet", "vyos_nat"],
                      self.fake.calls)

    def test_removing_wireless_interface_deletes_its_section(self):
        real_exists = os.path.exists
        with mock.patch.object(
                config_mod.os.path, "exists",
                side_effect=lambda path: path == "/etc/config/wireless"
                or real_exists(path)):
            cfg(self.cli,
                "set interfaces wireless wlan0 ssid home",
                "set interfaces wireless wlan0 security wpa2",
                "set interfaces wireless wlan0 passphrase secret123")
            self.commit()
            cfg(self.cli, "delete interfaces wireless wlan0")
            self.commit()
        self.assertIn(["uci", "delete", "wireless.vyos_wlan0"],
                      self.fake.uci_calls())

    def test_vyos_firewall_rules_render_to_nft(self):
        cfg(self.cli,
            "set firewall group address-group BLOCKED address 203.0.113.0/24",
            "set firewall ipv4 input filter rule 10 protocol tcp",
            "set firewall ipv4 input filter rule 10 destination port 22",
            "set firewall ipv4 input filter rule 10 action drop",
            "set firewall ipv4 input filter rule 10 log true")
        self.commit()
        path = os.path.join(self.cli.store.base_dir, "firewall.nft")
        text = open(path, encoding="utf-8").read()
        self.assertIn("table inet vyos_fw", text)
        self.assertIn("set addr4_BLOCKED", text)
        self.assertIn("meta nfproto ipv4", text)
        self.assertIn("tcp dport 22", text)
        self.assertIn("log prefix", text)
        self.assertIn("drop", text)
        self.assertIn(["nft", "-f", path], self.fake.calls)

    def test_frr_renders_ospf_rip_bfd(self):
        lines = self.cli.store.render_frr_conf(
            {}, {}, {}, "r1",
            ospf={"router-id": "10.0.0.1", "default-information": True,
                  "area": {"0": {"network": "10.0.0.0/8"}},
                  "interface": {"eth1": {"area": "0", "cost": 10,
                                         "passive": True}}},
            rip={"version": 2, "network": "192.168.0.0/16"},
            bfd={"interval": 300, "min-rx": 300, "multiplier": 3})
        text = "\n".join(lines)
        self.assertIn("router ospf", text)
        self.assertIn(" ospf router-id 10.0.0.1", text)
        self.assertIn(" network 10.0.0.0/8 area 0", text)
        self.assertIn(" interface eth1 area 0", text)
        self.assertIn(" ip ospf cost 10", text)
        self.assertIn(" passive-interface eth1", text)
        self.assertIn("router rip", text)
        self.assertIn(" network 192.168.0.0/16", text)
        self.assertIn("bfd", text)
        self.assertIn(" interval 300 min-rx 300 multiplier 3", text)

    def test_frr_renders_policy_lists_and_matches(self):
        lines = self.cli.store.render_frr_conf(
            {"local-as": 65001}, {"RM": {"permit": {"10": {
                "match": {"prefix-list": "PL"},
                "set": {"local-preference": 200}}}}}, {},
            "r1",
            prefix_lists={"PL": {"rule": {"10": {
                "action": "permit", "prefix": "10.0.0.0/8", "ge": 16}}}},
            as_path_lists={"ASP": {"rule": {"10": {
                "action": "permit", "regex": "^65001$"}}}},
            access_lists={"10": {"rule": {"10": {
                "action": "permit", "source": {"address": "192.0.2.0/24"}}}}})
        text = "\n".join(lines)
        self.assertIn("ip prefix-list PL seq 10 permit 10.0.0.0/8 ge 16", text)
        self.assertIn("ip as-path access-list ASP permit ^65001$", text)
        self.assertIn("access-list 10 permit 192.0.2.0/24", text)
        self.assertIn("match ip address prefix-list PL", text)
        self.assertIn("set local-preference 200", text)

    def test_router_advert_maps_to_odhcpd(self):
        cfg(self.cli,
            "set service router-advert interface lan managed-flag true",
            "set service router-advert interface lan default-lifetime 1800")
        self.commit()
        calls = self.fake.uci_calls()
        self.assertIn(["uci", "set", "dhcp.lan=dhcp"], calls)
        self.assertIn(["uci", "set", "dhcp.lan.ra=server"], calls)
        self.assertIn(["uci", "set", "dhcp.lan.dhcpv6=server"], calls)
        self.assertIn(["uci", "set", "dhcp.lan.ra_management=1"], calls)
        self.assertIn(["uci", "set", "dhcp.lan.ra_lifetime=1800"], calls)
        self.assertIn(["uci", "commit", "dhcp"], calls)
        self.assertIn(["/etc/init.d/odhcpd", "restart"], self.fake.calls)

    def test_router_advert_removal_restores_backup(self):
        cfg(self.cli,
            "set service router-advert interface lan managed-flag true")
        self.commit()
        cfg(self.cli, "delete service router-advert interface lan")
        self.commit()
        calls = self.fake.uci_calls()
        self.assertIn(["uci", "delete", "dhcp.lan.ra_management"], calls)
        self.assertIn(["uci", "commit", "dhcp"], calls)
        self.assertIn(["/etc/init.d/odhcpd", "restart"], self.fake.calls)

    def test_snmp_generates_uci_access(self):
        cfg(self.cli,
            "set service snmp community public authorization ro",
            "set service snmp contact admin@example.com",
            "set service snmp location lab",
            "set service snmp port 1610")
        self.commit()
        calls = self.fake.uci_calls()
        self.assertIn(["uci", "set", "snmpd.vyos_snmp_public_com=com2sec"],
                      calls)
        self.assertIn(["uci", "set", "snmpd.vyos_snmp_public_com.secname=ro"],
                      calls)
        self.assertIn(["uci", "set",
                       "snmpd.vyos_snmp_public_com.community=public"], calls)
        self.assertIn(["uci", "set",
                       "snmpd.vyos_snmp_public_access.write=none"], calls)
        self.assertIn(["uci", "set", "snmpd.agent.agentaddress=UDP:1610"],
                      calls)
        self.assertIn(["uci", "commit", "snmpd"], calls)
        self.assertIn(["/etc/init.d/snmpd", "restart"], self.fake.calls)

    def test_service_ntp_and_lldp(self):
        cfg(self.cli,
            "set service ntp server pool.ntp.org",
            "set service ntp server time.cloudflare.com",
            "set service lldp interface eth0",
            "set service lldp interface eth1",
            "set service lldp description edge")
        self.commit()
        calls = self.fake.uci_calls()
        self.assertIn(["uci", "add_list", "system.ntp.server=pool.ntp.org"],
                      calls)
        self.assertIn(["uci", "add_list",
                       "system.ntp.server=time.cloudflare.com"], calls)
        self.assertIn(["uci", "add_list", "lldpd.config.interface=eth0"], calls)
        self.assertIn(["uci", "add_list", "lldpd.config.interface=eth1"], calls)
        self.assertIn(["uci", "set",
                       "lldpd.config.lldp_description=edge"], calls)
        self.assertIn(["uci", "commit", "lldpd"], calls)
        self.assertIn(["/etc/init.d/sysntpd", "restart"], self.fake.calls)
        self.assertIn(["/etc/init.d/lldpd", "restart"], self.fake.calls)

    def test_pppoe_maps_to_netifd(self):
        cfg(self.cli,
            "set interfaces pppoe pppoe0 authentication username user@isp",
            "set interfaces pppoe pppoe0 authentication password secret",
            "set interfaces pppoe pppoe0 source-interface eth0",
            "set interfaces pppoe pppoe0 mtu 1492",
            "set interfaces pppoe pppoe0 no-peer-dns true")
        self.commit()
        calls = self.fake.uci_calls()
        self.assertIn(["uci", "set", "network.pppoe0=interface"], calls)
        self.assertIn(["uci", "set", "network.pppoe0.proto=pppoe"], calls)
        self.assertIn(["uci", "set", "network.pppoe0.device=eth0"], calls)
        self.assertIn(["uci", "set", "network.pppoe0.username=user@isp"], calls)
        self.assertIn(["uci", "set", "network.pppoe0.password=secret"], calls)
        self.assertIn(["uci", "set", "network.pppoe0.peerdns=0"], calls)
        self.assertIn(["uci", "commit", "network"], calls)

    def test_pppoe_removal_deletes_section(self):
        cfg(self.cli,
            "set interfaces pppoe pppoe0 source-interface eth0",
            "set interfaces pppoe pppoe0 authentication username u")
        self.commit()
        cfg(self.cli, "delete interfaces pppoe pppoe0")
        self.commit()
        self.assertIn(["uci", "delete", "network.pppoe0"], self.fake.calls)

    def test_syslog_remote_maps_to_logd(self):
        cfg(self.cli,
            "set system syslog remote 192.0.2.10 protocol tcp",
            "set system syslog remote 192.0.2.10 port 5514",
            "set system syslog local level info")
        self.commit()
        calls = self.fake.uci_calls()
        self.assertIn(["uci", "set", "system.@system[0].log_remote=1"], calls)
        self.assertIn(["uci", "set", "system.@system[0].log_ip=192.0.2.10"],
                      calls)
        self.assertIn(["uci", "set", "system.@system[0].log_port=5514"], calls)
        self.assertIn(["uci", "set", "system.@system[0].conloglevel=6"], calls)
        self.assertIn(["/etc/init.d/log", "restart"], self.fake.calls)

    def test_conntrack_and_sysctl_values(self):
        cfg(self.cli,
            "set system conntrack table-size 65536",
            "set system conntrack timeout tcp established 7440",
            "set system sysctl parameter net.ipv4.ip_forward value 1")
        self.commit()
        self.assertIn(["sysctl", "-w", "net.netfilter.nf_conntrack_max=65536"],
                      self.fake.calls)
        self.assertIn(["sysctl", "-w",
                       "net.netfilter.nf_conntrack_tcp_timeout_established=7440"],
                      self.fake.calls)
        self.assertIn(["sysctl", "-w", "net.ipv4.ip_forward=1"], self.fake.calls)
        self.assertTrue(os.path.exists(
            os.path.join(self.cli.store.base_dir, "sysctl.conf")))

    def test_watchdog_loads_module(self):
        cfg(self.cli,
            "set system watchdog module softdog",
            "set system watchdog timeout 30")
        self.commit()
        self.assertIn(["modprobe", "softdog"], self.fake.calls)

    def test_firewall_global_options_apply_sysctls_and_state(self):
        cfg(self.cli,
            "set firewall global-options syn-cookies true",
            "set firewall global-options state-policy established ACCEPT",
            "set firewall global-options state-policy invalid DROP",
            "set firewall ipv4 input filter rule 10 action drop")
        self.commit()
        text = open(os.path.join(self.cli.store.base_dir, "firewall.nft"),
                    encoding="utf-8").read()
        self.assertIn("ct state established,related accept", text)
        self.assertIn("ct state invalid drop", text)
        self.assertIn(["sysctl", "-w", "net.ipv4.tcp_syncookies=1"],
                      self.fake.calls)

    def test_removing_vyos_firewall_deletes_table(self):
        cfg(self.cli, "set firewall ipv4 input filter rule 10 action drop")
        self.commit()
        cfg(self.cli, "delete firewall ipv4")
        self.commit()
        self.assertIn(["nft", "delete", "table", "inet", "vyos_fw"],
                      self.fake.calls)
        self.assertFalse(os.path.exists(
            os.path.join(self.cli.store.base_dir, "firewall.nft")))

    def test_full_sync_skips_containers(self):
        cfg(self.cli, "set system host-name sync-test")
        self.commit()
        os.remove(self.cli.store.applied_path)
        called = []
        with mock.patch.object(self.cli.store, "_apply_containers",
                               side_effect=lambda old, new: called.append(1) or []):
            out = self.cli.store.sync()
        self.assertEqual(called, [])
        self.assertIn("containers untouched", out)

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

    def test_drift_is_recorded_and_detected(self):
        cfg(self.cli, "set system host-name drift-test")
        self.commit()
        self.assertTrue(os.path.exists(self.cli.store.applied_path))
        self.assertEqual(self.cli.store.drift(), [])
        # Simulate someone editing UCI behind vyoscli's back.
        self.fake.uci_show = "system.@system[0].hostname='changed-by-hand'"
        changed = dict(self.cli.store.drift())
        self.assertEqual(changed.get("system.@system[0]"), "changed")

    def test_sync_replays_only_the_drifted_owner(self):
        cfg(self.cli, "set system host-name sync-test")
        self.commit()
        manifest = load_json(self.cli.store.applied_path)
        section = "system.@system[0]"
        self.assertEqual(manifest[section]["owner"], "hostname")
        # Pretend that section was edited behind our back.
        manifest[section]["digest"] = "stale"
        self.cli.store._dump(self.cli.store.applied_path, manifest)
        before = len(self.fake.calls)
        out = self.cli.store.sync()
        self.assertIn("drift sections", out)
        self.assertIn("hostname -> sync-test", out)
        new_calls = self.fake.calls[before:]
        self.assertIn(["uci", "set", "system.@system[0].hostname=sync-test"],
                      new_calls)
        self.assertFalse(
            any(c[:2] == ["uci", "set"] and c[2].startswith("network.")
                for c in new_calls),
            "targeted sync must not touch network config")

    def test_sync_prunes_missing_sections(self):
        cfg(self.cli, "set system host-name sync-test")
        self.commit()
        manifest = load_json(self.cli.store.applied_path)
        manifest["network.ghost"] = {"owner": "interfaces", "digest": "x"}
        self.cli.store._dump(self.cli.store.applied_path, manifest)
        with mock.patch.object(self.cli.store, "_section_digest",
                               return_value="absent"):
            self.assertIn(("network.ghost", "missing"), self.cli.store.drift())
            self.cli.store.sync()
        remaining = load_json(self.cli.store.applied_path)
        self.assertNotIn("network.ghost", remaining)

    def test_sync_without_drift_is_a_noop(self):
        cfg(self.cli, "set system host-name sync-test")
        self.commit()
        before = len(self.fake.uci_statements())
        self.assertEqual(self.cli.store.sync(),
                         "Sync: no drift, nothing to do.")
        self.assertEqual(len(self.fake.uci_statements()), before)

    def test_sync_without_manifest_runs_full_pass(self):
        cfg(self.cli, "set system host-name sync-test")
        self.commit()
        os.remove(self.cli.store.applied_path)   # forget what was applied
        out = self.cli.store.sync()
        self.assertIn("full", out)
        self.assertIn("hostname -> sync-test", out)

    def test_no_manifest_means_no_drift_claim(self):
        self.assertIsNone(self.cli.store.drift())

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
