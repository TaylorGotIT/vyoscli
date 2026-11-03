"""Command-tree coverage.

* ``REACHABLE``  — VyOS-style paths that must resolve and store the right value.
* ``DOC_DRIFT``  — paths that docs/GUIDE.md advertises but the tree does not
  define at all (the command is rejected, so no silent misconfiguration).
* ``TODO``       — anything else known to be broken; empty today.

Keep this list in sync with docs/GUIDE.md: every documented path either appears
in REACHABLE or in DOC_DRIFT.
"""

from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from harness import cfg, cfg_errors, new_cli  # noqa: E402


REACHABLE = [
    ("set system host-name edge-1", ["system", "host-name"], "edge-1"),
    ("set system timezone Asia/Tokyo", ["system", "timezone"], "Asia/Tokyo"),
    ("set system ntp ntp.aliyun.com", ["system", "ntp"], ["ntp.aliyun.com"]),
    ("set system name-server 9.9.9.9", ["system", "name-server"], "9.9.9.9"),
    ("set system login user admin authentication plaintext-password Secret1",
     ["system", "login", "user", "admin", "authentication", "plaintext-password"],
     "Secret1"),
    ("set system login user admin authentication public-keys k1 key AAAAB3Nza",
     ["system", "login", "user", "admin", "authentication", "public-keys", "k1", "key"],
     "AAAAB3Nza"),
    ("set interfaces ethernet eth0 address 203.0.113.10/24",
     ["interfaces", "ethernet", "eth0", "address"], "203.0.113.10/24"),
    ("set interfaces ethernet eth0 mtu 9000",
     ["interfaces", "ethernet", "eth0", "mtu"], 9000),
    ("set interfaces ethernet eth0 disable true",
     ["interfaces", "ethernet", "eth0", "disable"], True),
    ("set interfaces ethernet eth0 vif 100 address 192.168.100.1/24",
     ["interfaces", "ethernet", "eth0", "vif", "100", "address"], "192.168.100.1/24"),
    ("set interfaces loopback lo address 10.0.0.1/32",
     ["interfaces", "loopback", "lo", "address"], "10.0.0.1/32"),
    ("set interfaces wireless wlan0 ssid home",
     ["interfaces", "wireless", "wlan0", "ssid"], "home"),
    ("set interfaces bridge br0 member eth1",
     ["interfaces", "bridge", "br0", "member"], "eth1"),
    ("set interfaces bridge br0 address 192.168.10.1/24",
     ["interfaces", "bridge", "br0", "address"], "192.168.10.1/24"),
    ("set interfaces bridge br0 vlan 10 tagged eth1",
     ["interfaces", "bridge", "br0", "vlan", "10", "tagged"], "eth1"),
    ("set interfaces dummy dum0 address 10.10.10.1/32",
     ["interfaces", "dummy", "dum0", "address"], "10.10.10.1/32"),
    ("set interfaces wireguard wg0 address 10.0.0.1/24",
     ["interfaces", "wireguard", "wg0", "address"], "10.0.0.1/24"),
    ("set interfaces wireguard wg0 peer PUBKEY allowed-ips 10.0.0.2/32",
     ["interfaces", "wireguard", "wg0", "peer", "PUBKEY", "allowed-ips"], "10.0.0.2/32"),
    ("set interfaces openvpn vtun0 mode server",
     ["interfaces", "openvpn", "vtun0", "mode"], "server"),
    ("set interfaces tunnel tun0 encapsulation gre",
     ["interfaces", "tunnel", "tun0", "encapsulation"], "gre"),
    ("set interfaces tunnel tun1 local-ip 192.0.2.1",
     ["interfaces", "tunnel", "tun1", "local-ip"], "192.0.2.1"),
    ("set interfaces tunnel tun1 remote-ip 198.51.100.1",
     ["interfaces", "tunnel", "tun1", "remote-ip"], "198.51.100.1"),
    ("set interfaces vxlan vxlan0 vni 42",
     ["interfaces", "vxlan", "vxlan0", "vni"], "42"),
    ("set protocols static route 10.0.0.0/8 next-hop 192.168.1.1",
     ["protocols", "static", "route", "10.0.0.0/8", "next-hop"], "192.168.1.1"),
    ("set protocols bgp local-as 65001", ["protocols", "bgp", "local-as"], 65001),
    ("set protocols bgp network 203.0.113.0/24",
     ["protocols", "bgp", "network"], "203.0.113.0/24"),
    ("set protocols bgp neighbor 10.0.0.2 remote-as 65002",
     ["protocols", "bgp", "neighbor", "10.0.0.2", "remote-as"], 65002),
    ("set protocols bgp peer-group PG1 remote-as 65003",
     ["protocols", "bgp", "peer-group", "PG1", "remote-as"], 65003),
    ("set protocols route-map RM1 permit 10 set local-preference 200",
     ["protocols", "route-map", "RM1", "permit", "10", "set", "local-preference"], 200),
    ("set policy community-list 10 rule 10 regex 65001:*",
     ["policy", "community-list", "10", "rule", "10", "regex"], "65001:*"),
    ("set policy route-redirect proxy rule 10 dport 80",
     ["policy", "route-redirect", "proxy", "rule", "10", "dport"], 80),
    ("set vrf name blue table 100", ["vrf", "name", "blue", "table"], 100),
    ("set vpn ipsec site-to-site peer 1.2.3.4 local-address 5.6.7.8",
     ["vpn", "ipsec", "site-to-site", "peer", "1.2.3.4", "local-address"], "5.6.7.8"),
    ("set vpn ipsec ike-group G1 proposal 10 encryption aes256",
     ["vpn", "ipsec", "ike-group", "G1", "proposal", "10", "encryption"], "aes256"),
    ("set service dhcp-server shared-network-name LAN subnet 192.168.1.0/24 "
     "default-router 192.168.1.1",
     ["service", "dhcp-server", "shared-network-name", "LAN", "subnet",
      "192.168.1.0/24", "default-router"], "192.168.1.1"),
    ("set service dhcp-server shared-network-name LAN subnet 192.168.1.0/24 "
     "range 0 start 192.168.1.100",
     ["service", "dhcp-server", "shared-network-name", "LAN", "subnet",
      "192.168.1.0/24", "range", "0", "start"], "192.168.1.100"),
    ("set service smartdns server upstream ip 1.1.1.1",
     ["service", "smartdns", "server", "upstream", "ip"], "1.1.1.1"),
    ("set service smartdns domain-set ads domain ads.example.com",
     ["service", "smartdns", "domain-set", "ads", "domain"], "ads.example.com"),
    ("set service crontab daily schedule '0 3 * * *'",
     ["service", "crontab", "daily", "schedule"], "0 3 * * *"),
    ("set service kcp t1 mode c", ["service", "kcp", "t1", "mode"], "c"),
    ("set service sqm interface eth0", ["service", "sqm", "interface"], "eth0"),
    ("set service ssh port 2222", ["service", "ssh", "port"], 2222),
    ("set service adguard enabled true", ["service", "adguard", "enabled"], True),
    ("set service dnsmasq port 5353", ["service", "dnsmasq", "port"], 5353),
    ("set service console-server ttyUSB0 speed 115200",
     ["service", "console-server", "ttyUSB0", "speed"], 115200),
    ("set service tcp-accelerate congestion-control bbr",
     ["service", "tcp-accelerate", "congestion-control"], "bbr"),
    ("set traffic-policy shaper wan interface eth0",
     ["traffic-policy", "shaper", "wan", "interface"], "eth0"),
    ("set firewall zone lan network lan", ["firewall", "zone", "lan", "network"], "lan"),
    ("set firewall forwarding fwd1 src lan",
     ["firewall", "forwarding", "fwd1", "src"], "lan"),
    ("set firewall rule 100 dest-port 22",
     ["firewall", "rule", "100", "dest-port"], 22),
    ("set nat source rule 100 out-interface wan",
     ["nat", "source", "rule", "100", "out-interface"], "wan"),
    ("set nat destination rule 10 port 8080",
     ["nat", "destination", "rule", "10", "port"], 8080),
    ("set container web image nginx:alpine",
     ["container", "web", "image"], "nginx:alpine"),
    ("set container web environment TZ value Asia/Shanghai",
     ["container", "web", "environment", "TZ", "value"], "Asia/Shanghai"),
]


# Documented in GUIDE.md, but the tree uses a different (VyOS-correct) name.
DOC_DRIFT = [
    "set interfaces ethernet eth0 role lan",              # tree: interfaces lan device eth0
    "set interfaces wireless wlan0 key secret123",        # tree: passphrase
    "set interfaces tunnel tun0 mode gre",                # tree: encapsulation gre
    "set interfaces openvpn vtun0 config-file /etc/x.conf",  # tree: explicit mode/proto/...
    "set service smartdns domain-rules-file /etc/list.txt",   # tree: domain-rule/domain-set
    "set service crontab daily command /tmp/x.sh",        # tree: script
]


TODO = []


def _get(cli, path):
    return cli.store.get(path)


class ReachablePathTest(unittest.TestCase):
    def setUp(self):
        self.cli = new_cli()

    def test_all_reachable_paths(self):
        for command, path, expected in REACHABLE:
            with self.subTest(command=command):
                errs = cfg_errors(self.cli, command)
                self.assertEqual(errs, [], f"{command} -> {errs}")
                value = _get(self.cli, path)
                if isinstance(value, list):
                    wanted = expected if isinstance(expected, list) else [expected]
                    for item in wanted:
                        self.assertIn(item, value)
                else:
                    self.assertEqual(value, expected)


class UnreachablePathTest(unittest.TestCase):
    def setUp(self):
        self.cli = new_cli()

    def assert_rejected(self, commands):
        for command in commands:
            with self.subTest(command=command):
                out = cfg(self.cli, command)[0]
                self.assertTrue(
                    out.startswith(("set: incomplete path", "set: invalid value")),
                    f"{command!r} unexpectedly succeeded (fix landed?) -> {out!r}",
                )

    def test_doc_drift_is_rejected_loudly(self):
        # Rename in GUIDE.md (or add the alias) — never let these silently store.
        self.assert_rejected(DOC_DRIFT)

    def test_todo_list_is_empty(self):
        self.assert_rejected(TODO)


if __name__ == "__main__":
    unittest.main(verbosity=2)
