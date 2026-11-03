"""Declarative config schema.

One definition per CLI path, used to generate the command tree (and later the
validators, help text and apply ownership). The rest of the tree is still built
by hand in ``commands.py`` and is migrated group by group; the tests check that
every spec resolves and stores a value.

Adding a path here replaces the equivalent hand-written ``Node(...)`` line and
keeps the type/help in one place.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional, Tuple

from .tree import Node


@dataclass(frozen=True)
class Spec:
    path: str                 # relative to the verb root, e.g. "system host-name"
    type: str = "str"         # value_type understood by tree.validate_value
    help: str = ""
    repeatable: bool = False  # stored as a list (matches DEFAULT_RUNNING)


SYSTEM: Tuple[Spec, ...] = (
    Spec("host-name", "host", "System hostname"),
    Spec("name-server", "ipv4",
         "Upstream DNS for dnsmasq (client queries)", repeatable=True),
    Spec("dns", "ipv4",
         "System resolver for router itself (/etc/resolv.conf)", repeatable=True),
    Spec("timezone", "str", "IANA timezone (e.g. Asia/Shanghai)"),
    Spec("domain-search", "str", "Domain search suffix (repeatable)",
         repeatable=True),
    Spec("ntp", "str", "NTP server hostname (repeatable)", repeatable=True),
    Spec("language", "str", "System locale (e.g. zh_cn, en)"),
    Spec("hardware vendor", "str", "Hardware vendor name"),
    Spec("hardware model", "str", "Hardware model"),
    Spec("hardware serial", "str", "Hardware serial number (S/N)"),
)

ETHERNET: Tuple[Spec, ...] = (
    Spec("address", "ipv4net", "IPv4 address/prefix", repeatable=True),
    Spec("description", "str", "Interface description"),
    Spec("mtu", "int", "MTU (default 1500)"),
    Spec("mac", "str", "MAC address"),
    Spec("duplex", "str", "Duplex mode: auto|half|full"),
    Spec("speed", "str", "Speed: auto|10|100|1000|2500|10000"),
    Spec("vrf", "str", "VRF instance name"),
    Spec("disable", "bool", "Administratively disable"),
)

SERVICE: Tuple[Spec, ...] = (
    Spec("ssh port", "port", "Listen port (default 22)"),
    Spec("ssh listen-address", "ipv4", "Bind address (default 0.0.0.0)"),
    Spec("ssh password-auth", "bool", "Allow password login (true/false)"),
    Spec("ssh root-login", "bool", "Allow root SSH login (true/false)"),
    Spec("ssh disable", "bool", "Disable SSH server"),
    Spec("adguard enabled", "bool", "Enable AdGuardHome"),
    Spec("adguard port", "port", "DNS listen port (default 53)"),
    Spec("adguard web-port", "port", "Web UI port (default 3000)"),
    Spec("adguard listen-address", "ipv4", "Bind IP (default 0.0.0.0)"),
    Spec("adguard disable", "bool", "Disable AdGuardHome"),
    Spec("adguard upstream", "str",
         "Upstream DNS (repeatable, configured in web UI)", repeatable=True),
    Spec("dnsmasq port", "port", "DNS listen port (default 53)"),
    Spec("dnsmasq listen-address", "ipv4", "Bind IP (default 0.0.0.0)"),
    Spec("dnsmasq disable", "bool", "Disable dnsmasq"),
    Spec("smartdns enabled", "bool", "Enable SmartDNS"),
    Spec("smartdns port", "port", "Listen port (default 5333)"),
    Spec("smartdns speed-check-mode", "str",
         "Probe mode, e.g. 'ping,tcp:80'"),
    Spec("smartdns forbid-aaaa", "bool", "Suppress IPv6 (AAAA) answers"),
    Spec("smartdns listen-address", "ipv4", "Bind IP (default 0.0.0.0)"),
    Spec("smartdns disable", "bool", "Disable smartdns"),
    Spec("tcp-accelerate congestion-control", "str", "bbr/cubic/hybla"),
    Spec("tcp-accelerate fq-codel", "bool", "Enable fq_codel qdisc"),
    Spec("sqm interface", "str", "WAN interface"),
    Spec("sqm download", "int", "Download bandwidth kbps"),
    Spec("sqm upload", "int", "Upload bandwidth kbps"),
    Spec("sqm qdisc", "str", "cake / fq_codel"),
)

BRIDGE: Tuple[Spec, ...] = (
    Spec("address", "ipv4net", "IP address/prefix", repeatable=True),
    Spec("description", "str", "Description"),
    Spec("member", "str", "Bridge member interfaces", repeatable=True),
    Spec("mac", "str", "MAC address"),
    Spec("mtu", "int", "MTU (default 1500)"),
    Spec("disable", "bool", "Administratively disable"),
    Spec("vrf", "str", "VRF instance name"),
    Spec("enable-vlan", "bool", "Enable VLAN aware bridge"),
    Spec("stp", "bool", "Enable spanning tree protocol"),
    Spec("priority", "int", "Bridge priority (default 32768)"),
    Spec("forwarding-delay", "int", "Forwarding delay (default 14)"),
    Spec("hello-time", "int", "Hello time (default 2)"),
    Spec("max-age", "int", "Max age (default 20)"),
    Spec("aging", "int", "MAC aging interval (default 300)"),
    Spec("mac-rebinding", "bool",
         "Enable transparent bridge (bump-in-the-wire)"),
)

TUNNEL: Tuple[Spec, ...] = (
    Spec("encapsulation", "str", "gre | ipip | sit | ip6ip6"),
    Spec("source-address", "ipv4", "Source outer IP"),
    Spec("source-interface", "str", "Source interface"),
    Spec("remote", "ipv4", "Tunnel remote address"),
    Spec("local-ip", "ipv4", "Source outer IP (legacy alias)"),
    Spec("remote-ip", "ipv4", "Tunnel remote address (legacy alias)"),
    Spec("address", "ipv4net", "Inner tunnel IPv4/prefix", repeatable=True),
    Spec("description", "str", "Description"),
    Spec("mtu", "int", "MTU (default 1476)"),
    Spec("disable", "bool", "Administratively disable"),
    Spec("vrf", "str", "VRF instance name"),
)

LOOPBACK: Tuple[Spec, ...] = (
    Spec("address", "ipv4net", "IP address/prefix", repeatable=True),
    Spec("description", "str", "Description"),
)

DUMMY: Tuple[Spec, ...] = (
    Spec("address", "ipv4net", "IP address/prefix", repeatable=True),
    Spec("description", "str", "Description"),
    Spec("mtu", "int", "MTU (default 1500)"),
    Spec("mac", "str", "MAC address"),
    Spec("disable", "bool", "Administratively disable"),
    Spec("vrf", "str", "VRF instance name"),
)

VXLAN: Tuple[Spec, ...] = (
    Spec("vni", "str", "VXLAN Network Identifier (1-16777215)"),
    Spec("local-ip", "ipv4", "Local outer IPv4"),
    Spec("remote-ip", "ipv4", "Remote outer IPv4"),
    Spec("address", "ipv4net", "Inner tunnel IPv4/prefix"),
)

FIREWALL_ZONE: Tuple[Spec, ...] = (
    Spec("network", "str", "UCI network name bound to zone"),
    Spec("input", "str", "Default input policy: ACCEPT/DROP/REJECT"),
    Spec("output", "str", "Default output policy: ACCEPT/DROP/REJECT"),
    Spec("forward", "str", "Default forward policy: ACCEPT/DROP/REJECT"),
)

FIREWALL_FORWARDING: Tuple[Spec, ...] = (
    Spec("src", "str", "Source zone"),
    Spec("dest", "str", "Destination zone"),
)

FIREWALL_RULE: Tuple[Spec, ...] = (
    Spec("name", "str", "Rule name"),
    Spec("src", "str", "Source zone (default *)"),
    Spec("dest-port", "port", "Destination port"),
    Spec("target", "str", "ACCEPT/DROP/REJECT"),
)

NAT_SOURCE_RULE: Tuple[Spec, ...] = (
    Spec("out-interface", "str", "Outgoing interface (e.g. wan)"),
    Spec("translation", "str", "Translation type (masquerade)"),
)

NAT_DEST_RULE: Tuple[Spec, ...] = (
    Spec("in-interface", "str", "Incoming interface (e.g. wan)"),
    Spec("port", "port", "External port"),
    Spec("to", "ipv4", "Internal IP to forward to"),
)

TEMPLATES = {
    "bridge": BRIDGE,
    "tunnel": TUNNEL,
    "loopback": LOOPBACK,
    "dummy": DUMMY,
    "vxlan": VXLAN,
    "firewall-zone": FIREWALL_ZONE,
    "firewall-forwarding": FIREWALL_FORWARDING,
    "firewall-rule": FIREWALL_RULE,
}

GROUPS = {
    "system": SYSTEM,
    "ethernet": ETHERNET,
    "service": SERVICE,
}


def attach(root: Node, specs: Iterable[Spec], action=None,
           prefix: str = "") -> None:
    """Add ``specs`` under ``root`` (``prefix`` is prepended to every path)."""
    for spec in specs:
        parts = (prefix + " " + spec.path).strip().split()
        node = root
        for part in parts:
            node = node.children.get(part) or node.add(Node(name=part))
        node.help = spec.help or node.help
        node.value_type = spec.type
        if action is not None:
            node.action = action


def template(specs: Iterable[Spec], help_text: str = "Per-interface config",
             action=None) -> Node:
    """Build a dynamic-node template whose children are the given specs."""
    tpl = Node(name="*", help=help_text)
    for spec in specs:
        node = Node(name=spec.path, value_type=spec.type, help=spec.help,
                    action=action)
        tpl.add(node)
    return tpl


def _keys_at(config: dict, path: tuple) -> list:
    cur = config
    for part in path:
        if not isinstance(cur, dict) or part not in cur:
            return []
        cur = cur[part]
    return list(cur.keys()) if isinstance(cur, dict) else []


def _attach_data(parent: Node, item: dict, action, path: tuple = (),
                 resolvable: bool = True, store=None) -> None:
    name = item["name"]
    node = Node(name=name, help=item.get("help", ""))
    children = item.get("children") or []
    if item.get("dyn"):
        template = Node(name="*", help=item.get("tpl_help", ""))
        for child in children:
            # Instances live under this node's config path, but their children
            # cannot be resolved without knowing a concrete instance name.
            _attach_data(template, child, action, path + (name,), False, store)
        if store is not None and resolvable:
            cfg_path = path + (name,)
            node.dynamic = lambda p=cfg_path: _keys_at(store.candidate, p)
        else:
            node.dynamic = lambda: []
        node._dyn_template = template  # type: ignore[attr-defined]
        parent.add(node)
        return
    if item.get("type") and not children:
        node.value_type = item["type"]
        node.action = action
        parent.add(node)
        return
    for child in children:
        _attach_data(node, child, action, path + (name,), resolvable, store)
    parent.add(node)


def build_tree(root: Node, data, action, store=None) -> Node:
    """Build a config subtree from config_tree.TREE (JSON data)."""
    for item in data:
        _attach_data(root, item, action, (), True, store)
    return root
