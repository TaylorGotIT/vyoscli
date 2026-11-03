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
from typing import Iterable, Tuple

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

GROUPS = {
    "system": SYSTEM,
    "ethernet": ETHERNET,
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
