#!/usr/bin/env python3
"""Generate config_tree.py from the authored schema/config-tree.json.

The JSON file is the source of truth; config_tree.py is a generated artifact.
Run this after editing the JSON, then regenerate docs:
  python3 scripts/build-config-tree.py
  python3 scripts/gen-command-reference.py
"""

from __future__ import annotations

import argparse
import json
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SOURCE = os.path.join(REPO, "schema", "config-tree.json")
TARGET = os.path.join(REPO, "package", "vyoscli", "files", "usr", "lib",
                      "vyoscli", "config_tree.py")

HEADER = '''"""GENERATED FILE - do not edit by hand.

Source: schema/config-tree.json
Regenerate: python3 scripts/build-config-tree.py
"""

import json

TREE = json.loads(r\'\'\''''

ALLOWED_TYPES = {"str", "string", "host", "ipv4", "ipv4net", "ipv4_cidr",
                 "ipv6", "ipv6net", "port", "integer", "int", "table",
                 "boolean", "bool"}


def validate(items, path=()):
    """Raise ValueError on structural problems; return number of nodes."""
    if not isinstance(items, list):
        raise ValueError(f"{'.'.join(path) or '<root>'}: expected a list")
    seen = set()
    count = 0
    for item in items:
        if not isinstance(item, dict):
            raise ValueError(f"{'.'.join(path)}: node is not an object")
        name = item.get("name")
        if not isinstance(name, str) or not name:
            raise ValueError(f"{'.'.join(path)}: empty node name")
        if name in seen:
            raise ValueError(f"{'.'.join(path + (name,))}: duplicate node")
        seen.add(name)
        children = item.get("children") or []
        has_type = "type" in item
        if has_type and item["type"] not in ALLOWED_TYPES:
            raise ValueError(f"{'.'.join(path + (name,))}: bad type "
                             f"{item['type']!r}")
        if item.get("dyn"):
            if not isinstance(item.get("tpl_help"), str):
                raise ValueError(f"{'.'.join(path + (name,))}: dyn without "
                                 "tpl_help")
            if has_type:
                raise ValueError(f"{'.'.join(path + (name,))}: dyn with type")
        if has_type and children:
            raise ValueError(f"{'.'.join(path + (name,))}: type and children")
        if item.get("repeatable") and not has_type:
            raise ValueError(f"{'.'.join(path + (name,))}: repeatable without "
                             "type")
        if not isinstance(item.get("help", ""), str):
            raise ValueError(f"{'.'.join(path + (name,))}: help is not a string")
        count += 1
        count += validate(children, path + (name,))
    return count


def render(tree) -> str:
    validate(tree)
    blob = json.dumps(tree, ensure_ascii=False, indent=0)
    if "'''" in blob:
        raise ValueError("tree data contains a triple quote")
    return HEADER + blob + "''')\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true",
                        help="fail if config_tree.py is out of date")
    args = parser.parse_args()
    with open(SOURCE, encoding="utf-8") as f:
        tree = json.load(f)
    text = render(tree)
    if args.check:
        try:
            with open(TARGET, encoding="utf-8") as f:
                current = f.read()
        except OSError:
            current = ""
        if current != text:
            print("config_tree.py is stale; run scripts/build-config-tree.py",
                  file=sys.stderr)
            return 1
        print("config_tree.py is up to date")
        return 0
    with open(TARGET, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    print(f"wrote {TARGET}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
