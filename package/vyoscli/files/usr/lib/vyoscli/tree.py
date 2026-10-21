"""VyOS-style command tree.

A CommandTree holds nested Node objects. Each Node corresponds to one token
on the CLI (e.g. "set", "interfaces", "ethernet", "eth0"). Leaf nodes that
accept a value declare a ``value_type`` and an ``action`` callback.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Tuple, Any


# Value types accepted at leaf nodes. They double as completion hints and
# lightweight validators.
VALUE_TYPES = {
    None: "command",
    "str": "<text>",
    "host": "<hostname>",
    "ipv4": "a.b.c.d",
    "ipv4net": "a.b.c.d/prefix",
    "port": "1-65535",
    "integer": "<0-2^31>",
    "boolean": "{true|false}",
}


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
        self.children[child.name] = child
        return child

    def walk(self, tokens: List[str]) -> Tuple["Node", List[str], int]:
        """Greedy-resolve ``tokens`` against this subtree.

        Returns (final_node, remaining_tokens, matched_count).
        Dynamic children are resolved on the fly.
        """
        node = self
        i = 0
        while i < len(tokens):
            tok = tokens[i]
            if tok in node.children:
                node = node.children[tok]
                i += 1
                continue
            # dynamic children: any token is accepted (used for
            # parametric nodes like ethX or CIDR prefixes). dynamic()
            # is only consulted for Tab completion hints.
            if node.dynamic is not None:
                synth = Node(name=tok, help="(dynamic)")
                tpl = getattr(node, "_dyn_template", None)
                if tpl is not None:
                    for k, v in tpl.children.items():
                        synth.children[k] = v
                    synth.value_type = tpl.value_type
                    synth.action = tpl.action
                node.children[tok] = synth
                node = synth
                i += 1
                continue
            break
        return node, tokens[i:], i


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
