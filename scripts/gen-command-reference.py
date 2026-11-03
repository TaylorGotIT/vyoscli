#!/usr/bin/env python3
"""Generate docs/COMMANDS.md from the generated config tree.

Every leaf path becomes one row: syntax, help text and a runnable example.
Run from the repo root:  python3 scripts/gen-command-reference.py
"""

from __future__ import annotations

import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "package", "vyoscli", "files", "usr", "lib"))

from vyoscli.config_tree import TREE  # noqa: E402

OUT = os.path.join(REPO, "docs", "COMMANDS.md")

SAMPLE = {
    "str": "text",
    "string": "text",
    "host": "edge-1",
    "ipv4": "192.0.2.1",
    "ipv4net": "192.0.2.1/24",
    "ipv4_cidr": "203.0.113.0/24",
    "port": "8080",
    "int": "100",
    "integer": "100",
    "bool": "true",
    "boolean": "true",
}

# Placeholder for a dynamic segment, keyed by the node that owns it.
PLACEHOLDER = {
    "ethernet": "<ifname>",
    "wireguard": "<wg-if>",
    "bridge": "<br-name>",
    "tunnel": "<tun-name>",
    "vxlan": "<vx-name>",
    "dummy": "<dum-name>",
    "loopback": "<lo>",
    "wireless": "<wlan-name>",
    "openvpn": "<vtun-name>",
    "peer": "<ip>",
    "zone": "<zone>",
    "forwarding": "<name>",
    "rule": "<id>",
    "shaper": "<policy>",
    "ike-group": "<group>",
    "esp-group": "<group>",
    "proposal": "<num>",
    "community-list": "<list-num>",
    "route-map": "<name>",
    "route": "<prefix>",
    "server": "<name>",
    "domain-set": "<name>",
    "domain-rule": "<name>",
    "address": "<domain>",
    "crontab": "<job>",
    "kcp": "<tunnel>",
    "console-server": "<device>",
    "shared-network-name": "<shared-name>",
    "subnet": "<cidr>",
    "range": "<id>",
    "static-mapping": "<name>",
    "container": "<name>",
    "environment": "<VAR>",
    "name": "<vrf>",
    "route-redirect": "<name>",
    "user": "<username>",
    "vif": "<vlan-id>",
    "public-keys": "<key-id>",
}


HINTS = (
    ("ACCEPT/DROP", "ACCEPT"),
    ("permit/deny", "permit"),
    ("wpa2", "wpa2"),
    ("bbr", "bbr"),
    ("always|on-failure", "always"),
    ("gre | ipip", "gre"),
    ("udp|tcp|tls|https", "udp"),
    ("server|client", "server"),
    ("fast2", "fast3"),
    ("cake", "cake"),
    ("c/client", "c"),
    ("ssh-rsa", "ssh-ed25519"),
    ("11g", "11g"),
    ("mbit", "100mbit"),
    ("IANA timezone", "Asia/Shanghai"),
    ("NTP server", "ntp.aliyun.com"),
    ("cron schedule", "0 3 * * *"),
    ("router-id", "10.0.0.1"),
)


def sample(help_text: str, value_type: str) -> str:
    lowered = help_text.lower()
    for needle, value in HINTS:
        if needle.lower() in lowered:
            return value
    return SAMPLE.get(value_type, "<value>")


def escape(text: str) -> str:
    return text.replace("|", "\\|")


def walk(items, path, rows):
    for item in items:
        name = item["name"]
        kids = item.get("children") or []
        if item.get("dyn"):
            placeholder = PLACEHOLDER.get(name, "<name>")
            walk(kids, path + [name, placeholder], rows)
            continue
        here = path + [name]
        if item.get("type") and not kids:
            value = sample(item.get("help", ""), item["type"])
            rows.append((" ".join(here), item.get("help", ""),
                         " ".join(here) + " " + value))
            continue
        walk(kids, here, rows)


def main() -> None:
    rows = []
    walk(TREE, [], rows)
    rows.sort(key=lambda row: row[0])

    groups = {}
    for cmd, help_text, example in rows:
        groups.setdefault(cmd.split()[0], []).append((cmd, help_text, example))

    lines = [
        "# vyoscli 命令参考",
        "",
        "> 本文件由 `python3 scripts/gen-command-reference.py` 从 `config_tree.py` 生成，请勿手改。",
        "",
        "所有 `set` 命令都有对应的 `delete <path>`；`edit <path>` 进入子节点后可以省略前缀。",
        "配置命令在 `configure` 之后执行，`commit` 生效。",
        "",
    ]
    for top, entries in groups.items():
        lines.append(f"## set {top}")
        lines.append("")
        lines.append("| 命令 | 说明 | 示例 |")
        lines.append("|---|---|---|")
        for cmd, help_text, example in entries:
            lines.append(f"| `{escape(cmd)}` | {escape(help_text)} | "
                         f"`{escape(example)}` |")
        lines.append("")
    with open(OUT, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines))
    print(f"wrote {OUT}: {len(rows)} commands")


if __name__ == "__main__":
    main()
