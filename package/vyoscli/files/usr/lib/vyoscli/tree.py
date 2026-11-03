"""VyOS-style command tree.

A CommandTree holds nested Node objects. Each Node corresponds to one token
on the CLI (e.g. "set", "interfaces", "ethernet", "eth0"). Leaf nodes that
accept a value declare a ``value_type`` and an ``action`` callback.
"""

from __future__ import annotations

import ipaddress
import re
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple


# Value types accepted at leaf nodes. They double as completion hints and
# lightweight validators.
VALUE_TYPES = {
    None: "command",
    "str": "<text>",
    "string": "<text>",
    "host": "<hostname>",
    "ipv4": "a.b.c.d",
    "ipv4net": "a.b.c.d/prefix",
    "ipv4_cidr": "a.b.c.d/prefix",
    "port": "1-65535",
    "integer": "<0-2^31>",
    "int": "<0-2^31>",
    "boolean": "{true|false}",
    "bool": "{true|false}",
}

_SCALAR_TYPES = {"ipv4", "ipv4net", "ipv4_cidr", "port", "integer", "int",
                 "boolean", "bool", "host"}


def validate_value(value_type: Optional[str], value: str) -> Optional[str]:
    """Validate a leaf value. Returns an error message, or None if valid."""
    if value_type not in _SCALAR_TYPES:
        return None
    if not value:
        return "value is required"
    if any(ch.isspace() for ch in value):
        return "expected a single token (unexpected extra words)"
    vt = value_type
    if vt == "ipv4":
        try:
            ipaddress.IPv4Address(value)
        except ValueError:
            return "not a valid IPv4 address"
    elif vt in ("ipv4net", "ipv4_cidr"):
        try:
            ipaddress.IPv4Network(value, strict=False)
        except ValueError:
            return "not a valid IPv4 prefix (a.b.c.d/nn)"
    elif vt == "port":
        if not re.fullmatch(r"\d+", value):
            return "not a port number"
        if not 1 <= int(value) <= 65535:
            return "port out of range 1-65535"
    elif vt in ("integer", "int"):
        if not re.fullmatch(r"-?\d+", value):
            return "not an integer"
    elif vt in ("boolean", "bool"):
        if value.lower() not in ("true", "false"):
            return "expected true or false"
    elif vt == "host":
        if not re.fullmatch(r"[A-Za-z0-9]([A-Za-z0-9._-]*[A-Za-z0-9])?", value):
            return "not a valid hostname"
    return None


def coerce_value(value_type: Optional[str], value: str) -> Any:
    """Store scalars with their native Python type (bool/int) like VyOS does."""
    if value_type in ("boolean", "bool"):
        return value.lower() == "true"
    if value_type in ("integer", "int", "port"):
        try:
            return int(value)
        except ValueError:
            return value
    return value


@dataclass
class Node:
    name: str
    help: str = ""
    # value_type: None => this node is not a value-bearing leaf (it has
    # children or is an executable command). Otherwise the token(s) after
    # the node path are consumed as its value.
    value_type: Optional[str] = None
    # action(mode_context, value) -> str output. None for structural nodes.
    action: Optional[Callable[[Any, Optional[str]], str]] = None
    children: Dict[str, "Node"] = field(default_factory=dict)
    # For parametric nodes (e.g. "eth0", "eth1" generated at runtime),
    # ``dynamic`` is a callable returning list of allowed names.
    dynamic: Optional[Callable[[], List[str]]] = None

    def add(self, child: "Node") -> "Node":
        """Attach a child; ``name=""`` declares a dynamic placeholder.

        A placeholder such as ``neighbor <ip>`` or ``user <name>`` describes
        the tokens the *parent* accepts, so it is stored as the parent's
        dynamic template instead of a literal child (which could never be
        matched by a real token).
        """
        if child.name == "":
            self.dynamic = child.dynamic if callable(child.dynamic) else (lambda: [])
            self._dyn_template = child
            return child
        self.children[child.name] = child
        return child

    def walk(self, tokens: List[str]) -> Tuple["Node", List[str], int, List[str]]:
        """Greedy-resolve ``tokens`` against this subtree.

        Returns ``(final_node, remaining_tokens, matched_count, canonical)``.
        ``canonical`` holds the *full* names that each consumed token resolved
        to, so an abbreviated command (``set syst host-name x``) can be stored
        under ``system.host-name`` instead of inventing a ``syst`` subtree.
        Dynamic children are resolved on the fly.
        """
        node = self
        i = 0
        canonical: List[str] = []
        while i < len(tokens):
            tok = tokens[i]
            if tok in node.children:
                canonical.append(tok)
                node = node.children[tok]
                i += 1
                continue
            # prefix match: unique child starting with tok
            matches = [c for c in node.children if c.startswith(tok)]
            if len(matches) == 1:
                canonical.append(matches[0])
                node = node.children[matches[0]]
                i += 1
                continue
            # dynamic children: any token is accepted (used for
            # parametric nodes like ethX or CIDR prefixes). dynamic()
            # is only consulted for Tab completion hints.
            if node.dynamic is not None:
                synth = Node(name=tok, help="(dynamic)")
                synth._synthetic = True  # type: ignore[attr-defined]
                tpl = getattr(node, "_dyn_template", None)
                if tpl is not None:
                    for k, v in tpl.children.items():
                        synth.children[k] = v
                    synth.value_type = tpl.value_type
                    synth.action = tpl.action
                node.children[tok] = synth
                canonical.append(tok)
                node = synth
                i += 1
                continue
            break
        return node, tokens[i:], i, canonical


class CommandTree:
    """Root container. Holds operational-mode roots and config-mode roots."""

    def __init__(self) -> None:
        self.op_root: Node = Node("(op)")
        self.cfg_root: Node = Node("(cfg)")

    def op(self, path: str, help: str = "", action=None, value_type=None) -> Node:
        return self._attach(self.op_root, path, help, action, value_type)

    def cfg(self, path: str, help: str = "", action=None, value_type=None) -> Node:
        return self._attach(self.cfg_root, path, help, action, value_type)

    @staticmethod
    def _attach(root: Node, path: str, help: str, action, value_type) -> Node:
        parts = path.strip().split()
        node = root
        for p in parts:
            if p not in node.children:
                node.add(Node(name=p))
            node = node.children[p]
        node.help = help or node.help
        if action is not None:
            node.action = action
        if value_type is not None:
            node.value_type = value_type
        return node

    def parametric(self, root: Node, path: str) -> Node:
        """Mark ``path`` as a dynamic parametric container.

        e.g. cfg("interfaces ethernet") then .parametric("eth*") template.
        The returned Node is the template; any token matching it at runtime
        gets a cloned subtree.
        """
        parts = path.strip().split()
        parent = root
        for p in parts:
            if p not in parent.children:
                parent.add(Node(name=p))
            parent = parent.children[p]
        template = Node(name="*", help="(dynamic interface)")
        parent.dynamic = lambda: ["eth0", "eth1", "eth2", "wlan0", "lo"]
        parent._dyn_template = template  # type: ignore[attr-defined]
        return template
