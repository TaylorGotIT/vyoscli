"""Configuration store.

Design rules (project-wide):
  1. Anything OpenWrt already exposes via UCI MUST go through UCI + reload
     the corresponding init script. Only when no UCI option exists do we
     drop to raw Linux commands (ip/iptables/sysctl...).
  2. Every commit takes a timestamped snapshot under history/. If the user
     runs ``commit confirmed [N]`` we fork a timer process; unless they run
     ``commit confirm`` within N minutes, the timer auto-rolls back to the
     snapshot. This protects remote admins from locking themselves out.

Layout on disk:
  /etc/vyoscli/running.json      # currently active config
  /etc/vyoscli/candidate.json   # uncommitted edits
  /etc/vyoscli/history/<ts>.json  # snapshots taken before each commit
  /etc/vyoscli/rollback.conf     # present iff a confirmed-commit timer is armed
"""

from __future__ import annotations

import glob
import hashlib
import ipaddress
import json
import os
import re
import copy
import shlex
import shutil
import subprocess
import sys
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple


DEFAULT_RUNNING: Dict[str, Any] = {
    "system": {
        "host-name": "OpenWrt",
        "name-server": ["1.1.1.1", "8.8.8.8"],
        "domain-search": [],
        "dns": [],   # system resolver (/etc/resolv.conf head)
        "timezone": "Asia/Shanghai",
        "ntp": ["ntp.aliyun.com", "cn.pool.ntp.org"],
        "language": "zh_cn",
        "login": {
            "user": {},   # name -> {full-name, password, disable, public-keys: {id: {key, type}}}
        },
        "hardware": {
            "vendor":  "",
            "model":   "",
            "serial":  "",
        },
    },
    "interfaces": {
        "ethernet": {
            "lo":   {"description": "loopback", "address": ["127.0.0.1/8"]},
            "eth0": {"description": "WAN",       "address": []},
            "eth1": {"description": "LAN",      "address": ["192.168.1.1/24"]},
        },
        "wireless": {},   # wlan0 -> {mode, ssid, channel, hw-mode, security, passphrase, network}
        "role": {},       # lan/wan -> ifname
        "bridge": {},     # br0 -> {member, address, stp, vlan: {vid: {untagged, tagged}}}
        "dummy": {},      # dum0 -> {address}
        "wireguard": {},  # wg0 -> {address, private-key, listen-port, peer: {}}
        "openvpn": {},    # vtun0 -> {mode, proto, port, dev, ca, cert, key, dh, server, push}
        "tunnel": {},     # tun0 -> {encapsulation, local-ip, remote-ip, address}
        "vxlan": {},      # vxlan0 -> {vni, local-ip, remote-ip, address}
        "loopback": {},   # lo -> {address, description}
    },
    "vpn": {
        "ipsec": {
            "ike-group": {},    # name -> {lifetime, proposal: {num: {encryption, hash, dh-group}}}
            "esp-group": {},    # name -> {lifetime, proposal: {num: {encryption, hash}}}
            "peer": {},         # remote-ip -> {local-address, remote-address, local-id, remote-id, secret, ike-group, esp-group, tunnel: {num: {local-prefix, remote-prefix}}}
            "remote-access": {
                "enabled": False,
                "local-id": "",
                "secret": "",
                "pool-start": "",
                "pool-end": "",
                "dns": []
            }
        }
    },
    "policy": {
        "route-redirect": {},   # name -> {rule: {num: {dport, redirect-to}}}
        "route-map": {},        # name -> {permit: {rule: {set, match}}}
        "community-list": {},   # num -> {rule: {regex, description, action}}
    },
    "vrf": {
        "name": {},   # name -> {table: int}
    },
    "traffic-policy": {
        "shaper": {},  # name -> {interface, bandwidth, per-ip}
    },
    "nat": {
        "source": {},       # rule-id -> {out-interface, translation}
        "destination": {},  # rule-id -> {in-interface, port, to}
    },
    "protocols": {
        "static": {
            "route": {},   # "10.0.0.0/8": {"next-hop": "192.168.1.1"}
        },
        "bgp": {
            "local-as": None,
            "router-id": None,
            "neighbor": {},   # ip -> {remote-as, description, route-map-in, route-map-out, peer-group}
            "peer-group": {},  # name -> {remote-as, update-source, route-map-import, soft-reconfiguration}
            "network": [],   # prefixes
        },
    },
    "service": {
        "ntp": {"server": []},
        "lldp": {"interface": []},
        "smartdns": {
            "enabled": False,
            "port": 5333,
            "speed-check-mode": "ping,tcp:80",
            "forbid-aaaa": True,
            "listen-address": "0.0.0.0",
            "server": {},       # name -> {ip, port, type}
            "domain-set": {},   # name -> {domain: [...], file}
            "domain-rule": {},  # name -> {domain-set, forward: [...]}
            "address": {},      # domain -> {ip}
        },
        "console-server": {},   # device -> {speed, ssh-port, description, alias}
        "tcp-accelerate": {
            "congestion-control": "bbr",   # bbr/cubic/hybla
            "fq-codel": True,   # key matches the command tree
        },
        "fec": {},   # UDPspeeder config
        "kcp": {},   # name -> {mode, local-listen-ip, local-listen-port, remote-listen-ip, remote-listen-port, destination-ip, destination-port, kcp-mode, key}

        "crontab": {},          # name -> {schedule, script, description}
        "dhcp-server": {        # VyOS shape: shared-network-name -> subnet -> options
            "shared-network-name": {},
        },
        "dnsmasq": {
            "port": 53,
            "listen-address": "0.0.0.0",
        },
        "adguard": {
            "enabled": False,
            "listen-address": "0.0.0.0",
            "port": 53,
            "web-port": 3000,
            "upstream": [],    # upstream DNS list
        },
        "ssh": {                # dropbear
            "port": 22,
            "listen-address": "0.0.0.0",
            "password-auth": True,
            "root-login": True,
        },
    },
    "container": {},            # name -> {image, network, port, volume, environment, restart, command}
    "firewall": {
        "zone": {},             # name -> {network, input, output, forward}
        "forwarding": {},       # name -> {src, dest}
        "rule": {},             # order-num -> {name, src, dest-port, target}
    },
}

HISTORY_KEEP = 20


def _as_list(value: Any) -> List[Any]:
    """Normalise a scalar-or-list config value into a list.

    Leaves accept a single value ("eth1"), but the UCI layer needs a list.
    Iterating the bare string was how ``untagged eth1`` became the ports
    ``e:u* t:u* h:u* 1:u*`` on a live router.
    """
    if value is None or value == "":
        return []
    if isinstance(value, (list, tuple)):
        return list(value)
    return [value]


def _format_pem(text: str) -> str:
    """Normalise a single-line PEM into the 64-column form OpenSSL expects."""
    text = str(text).strip()
    if "\n" in text:
        return text if text.endswith("\n") else text + "\n"
    match = re.match(r"^(-----BEGIN [A-Z0-9 ]+-----)(.*?)(-----END [A-Z0-9 ]+-----)$",
                     text)
    if not match:
        return text + "\n"
    body = re.sub(r"\s+", "", match.group(2))
    lines = [match.group(1)]
    lines += [body[i:i + 64] for i in range(0, len(body), 64)]
    lines.append(match.group(3))
    return "\n".join(lines) + "\n"


def _fw_slug(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9_]", "_", str(name))


def render_firewall_nft(fw: Dict[str, Any]) -> str:
    """Render the VyOS-style firewall tree into an nftables ruleset.

    Rules live in a dedicated ``inet vyos_fw`` table at priority -10, i.e. they
    run before OpenWrt's fw4 chains: they can drop/reject traffic early, while
    ``accept`` simply lets the packet continue to fw4 (and its zone policy).
    """
    lines = ["table inet vyos_fw {"]
    groups = fw.get("group") or {}

    def group_set(kind: str, set_type: str, prefix: str, field: str) -> None:
        for name, cfg in (groups.get(kind) or {}).items():
            values = _as_list((cfg or {}).get(field))
            if not values:
                continue
            elements = ", ".join(str(v) for v in values)
            lines.append(f"  set {prefix}_{_fw_slug(name)} {{ type {set_type}; "
                         f"elements = {{ {elements} }} }}")

    group_set("address-group", "ipv4_addr", "addr4", "address")
    group_set("ipv6-address-group", "ipv6_addr", "addr6", "address")
    group_set("port-group", "inet_service", "port", "port")
    group_set("interface-group", "ifname", "if", "interface")

    verdicts = {"accept": "accept", "drop": "drop", "reject": "reject"}
    chains: Dict[str, List[str]] = {"input": [], "forward": [], "output": []}
    for family in ("ipv4", "ipv6"):
        fam = fw.get(family) or {}
        nfproto = "ipv4" if family == "ipv4" else "ipv6"
        saddr = "ip saddr" if family == "ipv4" else "ip6 saddr"
        daddr = "ip daddr" if family == "ipv4" else "ip6 daddr"
        addr_prefix = "addr4" if family == "ipv4" else "addr6"
        for direction in ("input", "forward", "output"):
            rules = (((fam.get(direction) or {}).get("filter") or {})
                     .get("rule") or {})
            for num in sorted(rules, key=lambda n: int(n) if str(n).isdigit() else 0):
                rule = rules[num] or {}
                if not isinstance(rule, dict) or rule.get("disable"):
                    continue
                parts = [f"meta nfproto {nfproto}"]
                src = rule.get("source") or {}
                dst = rule.get("destination") or {}
                if src.get("address"):
                    parts.append(f"{saddr} {src['address']}")
                elif src.get("address-group"):
                    parts.append(f"{saddr} @{addr_prefix}_{_fw_slug(src['address-group'])}")
                if dst.get("address"):
                    parts.append(f"{daddr} {dst['address']}")
                proto = str(rule.get("protocol") or "").lower()
                port = dst.get("port")
                if port:
                    l4 = proto if proto in ("tcp", "udp") else "tcp"
                    parts.append(f"{l4} dport {port}")
                elif dst.get("port-group"):
                    l4 = proto if proto in ("tcp", "udp") else "tcp"
                    parts.append(f"{l4} dport @port_{_fw_slug(dst['port-group'])}")
                if rule.get("state"):
                    parts.append(f"ct state {rule['state']}")
                if direction in ("input", "forward") and rule.get("inbound-interface"):
                    parts.append(f'iifname "{rule["inbound-interface"]}"')
                if rule.get("log"):
                    parts.append(f'log prefix "vyos-{family}-{direction}-{num} "')
                parts.append(verdicts.get(str(rule.get("action", "accept")).lower(),
                                           "accept"))
                chains[direction].append("    " + " ".join(parts))

    state = (fw.get("global-options") or {}).get("state-policy") or {}
    state_rules: List[str] = []
    if str(state.get("established", "")).upper() == "ACCEPT":
        state_rules.append("    ct state established,related accept")
    if str(state.get("invalid", "")).upper() == "DROP":
        state_rules.append("    ct state invalid drop")

    for direction, body in chains.items():
        lines.append(f"  chain {direction} {{ type filter hook {direction} "
                     "priority -10; policy accept;")
        lines.extend(state_rules)
        lines.extend(body)
        lines.append("  }")
    lines.append("}")
    return "\n".join(lines) + "\n"



def render_nat_nft(nat: Dict[str, Any], family: str = "ipv4") -> str:
    """Render nat.source/destination rules into an inet vyos_nat table.

    The table sits at priority dstnat-10 / srcnat-10, i.e. before fw4's own
    NAT, so matched traffic uses these rules instead of the zone masquerade.
    """
    table = "vyos_nat66" if family == "ipv6" else "vyos_nat"
    lines = [f"table inet {table} {{"]
    prerouting: List[str] = []
    postrouting: List[str] = []

    def match_parts(rule: Dict[str, Any]) -> List[str]:
        parts = [f"meta nfproto {family}"]
        src = rule.get("source") or {}
        dst = rule.get("destination") or {}
        prefix = "ip6" if family == "ipv6" else "ip"
        if src.get("address"):
            parts.append(f"{prefix} saddr {src['address']}")
        if dst.get("address"):
            parts.append(f"{prefix} daddr {dst['address']}")
        proto = str(rule.get("protocol") or "").lower()
        l4 = proto if proto in ("tcp", "udp") else "tcp"
        if src.get("port"):
            parts.append(f"{l4} sport {src['port']}")
        if dst.get("port"):
            parts.append(f"{l4} dport {dst['port']}")
        if rule.get("inbound-interface"):
            parts.append(f'iifname "{rule["inbound-interface"]}"')
        if rule.get("out-interface"):
            parts.append(f'oifname "{rule["out-interface"]}"')
        return parts

    def target_of(address: Any, port: Any) -> str:
        text = str(address)
        if port:
            return f"[{text}]:{port}" if ":" in text else f"{text}:{port}"
        return text

    def rules_of(holder: Dict[str, Any]) -> Dict[str, Any]:
        rules = (holder or {}).get("rule")
        return rules if isinstance(rules, dict) else (holder or {})

    for rid, rule in sorted(rules_of(nat.get("source") or {}).items()):
        if not isinstance(rule, dict) or rule.get("disable"):
            continue
        translation = rule.get("translation")
        if isinstance(translation, dict):
            address = translation.get("address")
            port = translation.get("port")
        else:
            address, port = translation, None
        parts = match_parts(rule)
        if rule.get("log"):
            parts.append(f'log prefix "vyos-nat-src-{rid} "')
        if not address or str(address).lower() == "masquerade":
            parts.append("masquerade")
        else:
            parts.append(f"snat to {target_of(address, port)}")
        postrouting.append("    " + " ".join(parts))

    for rid, rule in sorted(rules_of(nat.get("destination") or {}).items()):
        if not isinstance(rule, dict) or rule.get("disable"):
            continue
        translation = rule.get("translation")
        if isinstance(translation, dict):
            address = translation.get("address")
            port = translation.get("port")
        else:
            address = translation or rule.get("to")
            port = rule.get("port")
        if not address:
            continue
        base = match_parts(rule)
        if rule.get("log"):
            base.append(f'log prefix "vyos-nat-dst-{rid} "')
        target = target_of(address, port)
        dnat = base + [f"dnat to {target}"]
        prerouting.append("    " + " ".join(dnat))
        if rule.get("hairpin"):
            hairpin_parts = [p for p in base if not p.startswith("iifname")]
            prerouting.append("    " + " ".join(
                hairpin_parts + [f"dnat to {target}"]))

    lines.append("  chain prerouting { type nat hook prerouting "
                 "priority dstnat - 10; policy accept;")
    lines.extend(prerouting)
    lines.append("  }")
    lines.append("  chain postrouting { type nat hook postrouting "
                 "priority srcnat - 10; policy accept;")
    lines.extend(postrouting)
    lines.append("  }")
    lines.append("}")
    return "\n".join(lines) + "\n"


def render_qos_commands(qos: Dict[str, Any]) -> List[List[str]]:
    """Translate qos policy/interface into tc commands."""
    policies = qos.get("policy") or {}
    commands: List[List[str]] = []

    def find(name: str):
        for kind, group in policies.items():
            if isinstance(group, dict) and isinstance(group.get(name), dict):
                return kind, group[name]
        return None, None

    for ifname, cfg in (qos.get("interface") or {}).items():
        if not isinstance(cfg, dict):
            continue
        egress = cfg.get("egress")
        if egress:
            kind, policy = find(str(egress))
            policy = policy or {}
            if kind == "fq-codel":
                cmd = ["tc", "qdisc", "replace", "dev", str(ifname), "root",
                       "fq_codel"]
                if policy.get("queue-limit"):
                    cmd += ["limit", str(policy["queue-limit"])]
                if policy.get("flows"):
                    cmd += ["flows", str(policy["flows"])]
                if policy.get("quantum"):
                    cmd += ["quantum", str(policy["quantum"])]
                if policy.get("target"):
                    cmd += ["target", f"{policy['target']}ms"]
                if policy.get("interval"):
                    cmd += ["interval", f"{policy['interval']}ms"]
                commands.append(cmd)
            elif kind == "cake":
                cmd = ["tc", "qdisc", "replace", "dev", str(ifname), "root",
                       "cake"]
                if policy.get("bandwidth"):
                    cmd += ["bandwidth", str(policy["bandwidth"])]
                if policy.get("flow-isolation"):
                    cmd += ["flow-isolation", str(policy["flow-isolation"])]
                if policy.get("rtt"):
                    cmd += ["rtt", f"{policy['rtt']}ms"]
                commands.append(cmd)
            elif kind == "shaper":
                default = policy.get("default") or {}
                rate = default.get("bandwidth") or policy.get("bandwidth")
                if rate:
                    commands.append(["tc", "qdisc", "replace", "dev", str(ifname),
                                     "root", "handle", "1:", "htb",
                                     "default", "10"])
                    commands.append(["tc", "class", "replace", "dev", str(ifname),
                                     "parent", "1:", "classid", "1:10",
                                     "htb", "rate", str(rate)])
                for cid, cls in (policy.get("class") or {}).items():
                    if not isinstance(cls, dict) or not cls.get("bandwidth"):
                        continue
                    cmd = ["tc", "class", "replace", "dev", str(ifname),
                           "parent", "1:", "classid", f"1:{cid}", "htb",
                           "rate", str(cls["bandwidth"])]
                    if cls.get("ceiling"):
                        cmd += ["ceil", str(cls["ceiling"])]
                    commands.append(cmd)
        ingress = cfg.get("ingress")
        if ingress:
            kind, policy = find(str(ingress))
            policy = policy or {}
            rate = ((policy.get("default") or {}).get("bandwidth")
                    or policy.get("bandwidth") or "1mbit")
            commands.append(["tc", "qdisc", "replace", "dev", str(ifname),
                             "handle", "ffff:", "ingress"])
            commands.append(["tc", "filter", "replace", "dev", str(ifname),
                             "parent", "ffff:", "protocol", "all", "u32",
                             "match", "u32", "0", "0", "police", "rate",
                             str(rate), "burst", "15k", "drop", "flowid", ":1"])
    return commands


def render_haproxy_cfg(lb: Dict[str, Any]) -> str:
    services = lb.get("service") or {}
    backends = lb.get("backend") or {}
    maxconn = (lb.get("global-parameters") or {}).get("max-connections")
    lines = ["global"]
    if maxconn:
        lines.append(f"    maxconn {maxconn}")
    lines += ["", "defaults", "    mode tcp", "    timeout connect 5s",
              "    timeout client 30s", "    timeout server 30s", ""]
    backend_mode: Dict[str, str] = {}
    for name, svc in services.items():
        if not isinstance(svc, dict):
            continue
        mode = str(svc.get("mode") or "tcp")
        addr = svc.get("listen-address") or "0.0.0.0"
        port = svc.get("port") or 80
        lines.append(f"frontend {name}")
        lines.append(f"    bind {addr}:{port}")
        lines.append(f"    mode {mode}")
        if svc.get("backend"):
            lines.append(f"    default_backend {svc['backend']}")
            backend_mode.setdefault(str(svc["backend"]), mode)
        lines.append("")
    for name, be in backends.items():
        if not isinstance(be, dict):
            continue
        mode = backend_mode.get(str(name), "tcp")
        lines.append(f"backend {name}")
        lines.append(f"    mode {mode}")
        lines.append(f"    balance {be.get('balance') or 'roundrobin'}")
        for sname, srv in (be.get("server") or {}).items():
            if not isinstance(srv, dict) or not srv.get("address"):
                continue
            entry = f"    server {sname} {srv['address']}:{srv.get('port') or 80}"
            if srv.get("weight"):
                entry += f" weight {srv['weight']}"
            if srv.get("check"):
                entry += " check"
            lines.append(entry)
        lines.append("")
    return "\n".join(lines) + "\n"


class ConfigStore:
    def __init__(self, base_dir: str = "/etc/vyoscli") -> None:
        self.base_dir = base_dir
        self.running_path = os.path.join(base_dir, "running.json")
        self.candidate_path = os.path.join(base_dir, "candidate.json")
        self.applied_path = os.path.join(base_dir, "applied.json")
        self.history_dir = os.path.join(base_dir, "history")
        self.rollback_conf = os.path.join(base_dir, "rollback.conf")
        self.running: Dict[str, Any] = {}
        self.candidate: Dict[str, Any] = {}
        # UCI sections written by the current apply pass: section -> owner step
        self._touched: Dict[str, str] = {}
        self._current_owner: Optional[str] = None
        self.load()

    # ---------- persistence ----------
    def load(self) -> None:
        os.makedirs(self.base_dir, exist_ok=True)
        os.makedirs(self.history_dir, exist_ok=True)
        # Conventional subdirectories, all migrated together with the config.
        os.makedirs(os.path.join(self.base_dir, "scripts"), exist_ok=True)
        os.makedirs(os.path.join(self.base_dir, "lists"), exist_ok=True)
        if os.path.exists(self.running_path):
            with open(self.running_path, "r", encoding="utf-8") as f:
                self.running = json.load(f)
        else:
            self.running = copy.deepcopy(DEFAULT_RUNNING)
            self._dump(self.running_path, self.running)
        if os.path.exists(self.candidate_path):
            with open(self.candidate_path, "r", encoding="utf-8") as f:
                self.candidate = json.load(f)
        else:
            self.candidate = copy.deepcopy(self.running)
            self._dump(self.candidate_path, self.candidate)

    @staticmethod
    def _dump(path: str, data: Dict[str, Any]) -> None:
        """Write JSON atomically with 0600 perms (the config holds secrets)."""
        tmp = f"{path}.tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, sort_keys=True)
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())
        try:
            os.chmod(tmp, 0o600)
        except OSError:
            pass
        os.replace(tmp, path)

    def _persist_candidate(self) -> None:
        self._dump(self.candidate_path, self.candidate)

    # ---------- path helpers ----------
    @staticmethod
    def _nav(d: Dict[str, Any], path: List[str], create: bool = False) -> Optional[Dict[str, Any]]:
        cur: Any = d
        for p in path:
            if not isinstance(cur, dict):
                return None
            if p not in cur:
                if not create:
                    return None
                cur[p] = {}
            cur = cur[p]
        return cur

    def get(self, path: List[str], candidate: bool = True) -> Any:
        root = self.candidate if candidate else self.running
        cur: Any = root
        for p in path:
            if not isinstance(cur, dict) or p not in cur:
                return None
            cur = cur[p]
        return cur

    @staticmethod
    def _default_is_list(path: List[str]) -> bool:
        """True when DEFAULT_RUNNING declares this path as a repeatable list."""
        cur: Any = DEFAULT_RUNNING
        for part in path:
            if not isinstance(cur, dict) or part not in cur:
                return False
            cur = cur[part]
        return isinstance(cur, list)

    def set_value(self, path: List[str], value: Any) -> None:
        if not path:
            return
        *parents, leaf = path
        node = self._nav(self.candidate, parents, create=True)
        if node is None:
            return
        existing = node.get(leaf)
        if isinstance(existing, list):
            if value not in existing:
                existing.append(value)
        elif existing is None and leaf not in node and self._default_is_list(path):
            # Repeatable leaves (name-server, ntp, address, push...) must stay
            # lists even when the running config predates the key; storing a
            # bare string here is what turned 223.5.5.5 into 2 2 3 . 5 . 5 . 5.
            node[leaf] = [value]
        else:
            node[leaf] = value
        self._persist_candidate()

    def append_value(self, path: List[str], value: Any) -> None:
        """Append to a repeatable leaf without nesting the list into itself."""
        if not path:
            return
        *parents, leaf = path
        node = self._nav(self.candidate, parents, create=True)
        if node is None:
            return
        current = node.get(leaf) if leaf in node else None
        if current is None:
            node[leaf] = [value]
        elif isinstance(current, list):
            if value not in current:
                current.append(value)
        elif current != value:
            node[leaf] = [current, value]
        self._persist_candidate()

    def create_node(self, path: List[str]) -> None:
        """Materialise a structural (valueless) node in the candidate."""
        if path:
            self._nav(self.candidate, path, create=True)
            self._persist_candidate()

    def delete_path(self, path: List[str]) -> None:
        if not path:
            return
        *parents, leaf = path
        node = self._nav(self.candidate, parents, create=False)
        if isinstance(node, dict) and leaf in node:
            del node[leaf]
        elif isinstance(node, list) and leaf in node:
            node.remove(leaf)
        self._persist_candidate()

    # ---------- transactions ----------
    def modified(self) -> bool:
        return self.candidate != self.running

    # ---------- UCI helpers ----------
    @staticmethod
    def _have_uci() -> bool:
        return shutil.which("uci") is not None

    def _uci(self, *args: str) -> subprocess.CompletedProcess:
        if args and args[0] in ("set", "add_list", "delete", "del_list"):
            target = args[1].split("=", 1)[0]
            parts = target.split(".")
            if len(parts) >= 2:
                self._touched[f"{parts[0]}.{parts[1]}"] = self._current_owner or ""
        return subprocess.run(["uci", *args], check=True,
                              capture_output=True, text=True)

    @staticmethod
    def _section_digest(section: str) -> str:
        """Fingerprint one UCI section, or 'absent' when it does not exist."""
        try:
            r = subprocess.run(["uci", "show", section], capture_output=True,
                               text=True, timeout=5)
        except OSError:
            return "unavailable"
        if r.returncode != 0:
            return "absent"
        return hashlib.sha256(r.stdout.encode()).hexdigest()

    def _load_applied(self) -> Dict[str, Any]:
        try:
            with open(self.applied_path, encoding="utf-8") as f:
                data = json.load(f)
            return data if isinstance(data, dict) else {}
        except (OSError, ValueError):
            return {}

    def _record_applied(self) -> None:
        """Remember what commit actually wrote, so later drift is detectable.

        The manifest accumulates across commits: a section written once stays
        tracked until a later commit rewrites it (or records it as absent).
        Each entry stores the owning apply step so `sync` can replay just the
        affected groups instead of reloading everything.
        """
        manifest = self._load_applied()
        for section, owner in self._touched.items():
            manifest[section] = {"owner": owner,
                                 "digest": self._section_digest(section)}
        self._dump(self.applied_path, manifest)

    @staticmethod
    def _manifest_digest(entry: Any) -> Any:
        # applied.json from older builds stored a bare digest string.
        return entry.get("digest") if isinstance(entry, dict) else entry

    def drift(self) -> Optional[List[Tuple[str, str]]]:
        """Sections whose UCI content changed since the last commit.

        Returns None when no manifest exists yet, else [(section, state)] where
        state is "changed" or "missing".
        """
        if not os.path.exists(self.applied_path):
            return None
        manifest = self._load_applied()
        changed: List[Tuple[str, str]] = []
        for section, entry in sorted(manifest.items()):
            now = self._section_digest(section)
            if now != self._manifest_digest(entry):
                changed.append((section, "missing" if now == "absent" else "changed"))
        return changed

    def _find_uci_section(self, config: str, option: str, value: str) -> Optional[str]:
        try:
            out = self._uci("show", config)
        except Exception:
            return None
        for line in out.stdout.splitlines():
            head, _, rest = line.partition(".")
            section, _, keyval = rest.partition(".")
            key, _, val = keyval.partition("=")
            if key == option and val.strip("'\"") == value:
                return section
        return None

    # ---------- apply: old running -> new running ----------
    def _address_port_in_use(self, ip: str, port: int) -> bool:
        if os.environ.get("VYOSCLI_SKIP_PORT_CHECK") == "1":
            return False
        """Return True if binding (ip, port) conflicts with an existing listener."""
        try:
            r = subprocess.run(["ss", "-tulnp"], capture_output=True, text=True, timeout=5)
        except Exception:
            return False
        for line in r.stdout.splitlines()[1:]:
            parts = line.split()
            if len(parts) < 5:
                continue
            local = parts[4]
            if ":" not in local:
                continue
            lip, _, lport = local.rpartition(":")
            try:
                lport = int(lport)
            except ValueError:
                continue
            if lport != port:
                continue
            if lip in ("0.0.0.0", "*", "::") or lip == ip or ip == "0.0.0.0":
                return True
        return False

    def _check_dns_conflicts(self, new: Dict[str, Any]) -> List[str]:
        """Detect port conflicts among dnsmasq/smartdns/adguardhome."""
        problems = []
        svc = new.get("service") or {}
        # (name, ip, port)
        candidates = []
        dm = svc.get("dnsmasq") or {}
        candidates.append(("dnsmasq", dm.get("listen-address", "0.0.0.0"),
                            int(dm.get("port", 53))))
        sd = svc.get("smartdns") or {}
        if sd.get("enabled"):
            candidates.append(("smartdns", sd.get("listen-address", "0.0.0.0"),
                                int(sd.get("port", 5333))))
        ag = svc.get("adguard") or {}
        if ag.get("enabled"):
            candidates.append(("adguardhome", ag.get("listen-address", "0.0.0.0"),
                                int(ag.get("port", 53))))
        # duplicates among candidates (same ip:port)
        seen = {}
        for name, ip, port in candidates:
            key = (ip, port)
            if key in seen:
                problems.append(
                    f"CONFLICT: {seen[key]} and {name} both want {ip}:{port}.")
            seen[key] = name
        # real port check (ss -tulnp)
        for name, ip, port in candidates:
            if self._address_port_in_use(ip, port):
                problems.append(
                    f"PORT IN USE: {name} wants {ip}:{port} but something is already listening there.")
        return problems

    def _apply_steps(self):
        """Ordered (owner, method) pairs; the owner names land in applied.json."""
        return [
            ("hostname", self._apply_hostname),
            ("system-meta", self._apply_system_meta),
            ("system-extra", self._apply_system_extra),
            ("ntp", self._apply_ntp),
            ("snmp", self._apply_snmp),
            ("router-advert", self._apply_router_advert),
            ("lldp", self._apply_lldp),
            ("name-servers", self._apply_name_servers),
            ("system-dns", self._apply_system_dns),
            ("login", self._apply_login),
            ("interfaces", self._apply_interfaces),
            ("pppoe", self._apply_pppoe),
            ("virtual-ifaces", self._apply_virtual_ifaces),
            ("bonding", self._apply_bonding),
            ("macsec", self._apply_macsec),
            ("vrrp", self._apply_vrrp),
            ("openconnect", self._apply_openconnect),
            ("l2tp", self._apply_l2tp),
            ("dhcp-relay", self._apply_dhcp_relay),
            ("pki", self._apply_pki),
            ("https", self._apply_https),
            ("flow-accounting", self._apply_flow_accounting),
            ("qos", self._apply_qos),
            ("haproxy", self._apply_haproxy),
            ("wan-lb", self._apply_wan_lb),
            ("wireless", self._apply_wireless),
            ("interface-roles", self._apply_interface_roles),
            ("vrf", self._apply_vrf),
            ("static-routes", self._apply_static_routes),
            ("static-tables", self._apply_static_tables),
            ("local-route", self._apply_local_route),
            ("tcp-mss", self._apply_tcp_mss),
            ("mtr", self._apply_mtr),
            ("bgp", self._apply_bgp),
            ("policy", self._apply_policy),
            ("firewall", self._apply_firewall),
            ("firewall15", self._apply_firewall15),
            ("nat", self._apply_nat),
            ("nat66", self._apply_nat66),
            ("wireguard", self._apply_wireguard),
            ("openvpn", self._apply_openvpn),
            ("tunnel", self._apply_tunnel),
            ("vxlan", self._apply_vxlan),
            ("ipsec", self._apply_ipsec),
            ("dhcp", self._apply_dhcp),
            ("ssh", self._apply_ssh),
            ("ssh-acl", self._apply_ssh_acl),
            ("adguard", self._apply_adguard),
            ("dnsmasq", self._apply_dnsmasq),
            ("smartdns", self._apply_smartdns),
            ("traffic-policy", self._apply_traffic_policy),
            ("sqm", self._apply_sqm),
            ("kcp", self._apply_kcp),
            ("tcp-accelerate", self._apply_tcp_accelerate),
            ("console-server", self._apply_console_server),
            ("containers", self._apply_containers),
            ("crontab", self._apply_crontab),
            ("service-disable", self._apply_service_disable),
        ]

    def _apply_all(self, old: Dict[str, Any], new: Dict[str, Any],
                   only: Optional[set] = None,
                   skip: Optional[set] = None) -> List[str]:
        """按依赖优先级下发配置：system -> interfaces -> protocols -> vpn -> service

        ``only`` restricts the pass to the given owner names (used by a targeted
        ``sync``); ``None`` runs everything.
        """
        notes: List[str] = []
        if not self._have_uci():
            notes.append("(no uci on this host, changes kept in vyoscli JSON only)")
            return notes
        skip = skip or set()
        for owner, step in self._apply_steps():
            if only is not None and owner not in only:
                continue
            if owner in skip:
                continue
            self._current_owner = owner
            notes.extend(step(old, new))
        self._current_owner = None
        return notes

    def _iface_sections(self, ifname: str) -> List[str]:
        """Network sections referencing this device (IPv4 before IPv6)."""
        secs = {}
        try:
            text = self._uci("show", "network").stdout
        except Exception:
            return []
        for line in text.splitlines():
            lhs, _, raw = line.partition("=")
            if not lhs.startswith("network."):
                continue
            path = lhs[len("network."):]
            if "." in path:
                sec, key = path.split(".", 1)
                secs.setdefault(sec, {})[key] = raw.strip("'\"")
            else:
                secs.setdefault(path, {})["__type__"] = raw.strip("'\"")
        found = [sec for sec, opts in secs.items()
                 if opts.get("__type__") == "interface"
                 and (opts.get("device") == ifname
                      or opts.get("ifname") == ifname)]
        found.sort(key=lambda sec: "dhcpv6" in secs[sec].get("proto", ""))
        return found

    def _network_map(self) -> Dict[str, Dict[str, Any]]:
        """Map device name -> the UCI section that owns it.

        ``direct`` means the interface references the device itself
        (``network.wan.device='eth1'``); ``direct=False`` means the device is a
        port of a bridge (``eth0`` in ``br-lan``), which is L2-only from
        netifd's point of view.
        """
        secs: Dict[str, Dict[str, str]] = {}
        try:
            text = self._uci("show", "network").stdout
        except Exception:
            return {}
        for line in text.splitlines():
            lhs, _, raw = line.partition("=")
            if not lhs.startswith("network."):
                continue
            path = lhs[len("network."):]
            if "." in path:
                sec, key = path.split(".", 1)
                secs.setdefault(sec, {})[key] = raw.strip("'\"")
            else:
                secs.setdefault(path, {})["__type__"] = raw.strip("'\"")

        mapping: Dict[str, Dict[str, Any]] = {}
        for sec, opts in secs.items():
            if opts.get("__type__") != "interface":
                continue
            dev = opts.get("device") or opts.get("ifname")
            if dev:
                mapping[dev] = {"section": sec, "proto": opts.get("proto", ""),
                                "direct": True}
        # devices (bridges) are shared by every port; the owning interface is
        # whichever section references the bridge as its device.
        for sec, opts in secs.items():
            if opts.get("__type__") != "device" or opts.get("type") != "bridge":
                continue
            bridge = opts.get("name") or sec
            owner = mapping.get(bridge)
            if not owner:
                continue
            for port in (opts.get("ports") or "").split():
                port = port.split(":")[0]
                mapping.setdefault(port, {"section": owner["section"],
                                          "proto": owner["proto"],
                                          "direct": False})
        return mapping

    # ---------- interface takeover backup ----------
    def _backup_path(self, section: str) -> str:
        return os.path.join(self.base_dir, "backup", f"network.{section}.json")

    @staticmethod
    def _uci_get(key: str) -> Optional[str]:
        try:
            proc = subprocess.run(["uci", "-q", "get", key],
                                  capture_output=True, text=True, timeout=5)
        except OSError:
            return None
        return proc.stdout.strip() if proc.returncode == 0 else None

    def _section_exists(self, section: str) -> bool:
        return self._uci_get(f"network.{section}") is not None

    def _backup_section(self, section: str) -> None:
        """Remember the options we are about to overwrite (first takeover)."""
        path = self._backup_path(section)
        if os.path.exists(path):
            return
        data = {}
        for opt in ("proto", "ipaddr", "device", "ifname"):
            value = self._uci_get(f"network.{section}.{opt}")
            if value:
                data[opt] = value
        if data:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            self._dump(path, data)

    def _restore_section(self, section: str, notes: List[str]) -> None:
        path = self._backup_path(section)
        data = {}
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, ValueError):
            data = {}
        for opt in ("proto", "device", "ifname"):
            if data.get(opt):
                self._uci("set", f"network.{section}.{opt}={data[opt]}")
            else:
                try:
                    self._uci("delete", f"network.{section}.{opt}")
                except subprocess.CalledProcessError:
                    pass
        try:
            self._uci("delete", f"network.{section}.ipaddr")
        except subprocess.CalledProcessError:
            pass
        for value in str(data.get("ipaddr", "")).split():
            self._uci("add_list", f"network.{section}.ipaddr={value}")
        self._remove_quietly(path)
        notes.append(f"released network.{section} (restored original settings)")

    def _release_iface(self, ifname: str, mapping: Dict[str, Dict[str, Any]],
                       notes: List[str]) -> None:
        section = (mapping.get(ifname) or {}).get("section")
        if section and os.path.exists(self._backup_path(section)):
            self._restore_section(section, notes)
            return
        ours = f"vyos_{ifname}"
        if section == ours or self._section_exists(ours):
            try:
                self._uci("delete", f"network.{ours}")
            except subprocess.CalledProcessError:
                pass
            notes.append(f"{ifname}: removed network.{ours}")

    def _apply_local_route(self, old, new):
        old_r = (((old.get("policy") or {}).get("local-route") or {})
                 .get("rule") or {})
        new_r = (((new.get("policy") or {}).get("local-route") or {})
                 .get("rule") or {})
        if old_r == new_r:
            return []
        state_path = os.path.join(self.base_dir, "local-route.json")
        try:
            with open(state_path, encoding="utf-8") as f:
                applied = json.load(f)
        except (OSError, ValueError):
            applied = []
        wanted = []
        notes = []
        for num, rule in new_r.items():
            if not isinstance(rule, dict):
                continue
            source = rule.get("source")
            table = (rule.get("set") or {}).get("table")
            if not source or not table:
                continue
            subprocess.run(["ip", "rule", "add", "from", str(source),
                            "lookup", str(table), "priority", str(num)],
                           capture_output=True, text=True, timeout=10)
            wanted.append(str(num))
            notes.append(f"local-route: {source} -> table {table} (prio {num})")
        for prio in applied:
            if prio not in wanted:
                subprocess.run(["ip", "rule", "del", "priority", str(prio)],
                               capture_output=True, text=True, timeout=10)
        os.makedirs(self.base_dir, exist_ok=True)
        with open(state_path, "w", encoding="utf-8") as f:
            json.dump(wanted, f)
        return notes

    def _apply_static_tables(self, old, new):
        old_t = (((old.get("protocols") or {}).get("static") or {})
                 .get("table") or {})
        new_t = (((new.get("protocols") or {}).get("static") or {})
                 .get("table") or {})
        if old_t == new_t:
            return []
        state_path = os.path.join(self.base_dir, "static-tables.json")
        try:
            with open(state_path, encoding="utf-8") as f:
                applied = json.load(f)
        except (OSError, ValueError):
            applied = []
        wanted = []
        notes = []
        for table, body in new_t.items():
            try:
                table_id = int(table)
            except (TypeError, ValueError):
                table_id = 0
            if not 1 <= table_id <= 4294967295:
                notes.append(f"static-table {table}: invalid table ID "
                             f"(1-4294967295)")
                continue
            routes = (body or {}).get("route") or {}
            for prefix, route in routes.items():
                if not isinstance(route, dict):
                    continue
                args = ["ip", "route", "replace", "table", str(table),
                        str(prefix)]
                if route.get("blackhole"):
                    args.append("blackhole")
                elif route.get("next-hop"):
                    args += ["via", str(route["next-hop"])]
                elif route.get("interface"):
                    args += ["dev", str(route["interface"])]
                else:
                    continue
                subprocess.run(args, capture_output=True, text=True,
                               timeout=10)
                wanted.append(f"{table}|{prefix}")
                notes.append(f"static-table {table}: {prefix}")
        for item in applied:
            if item in wanted:
                continue
            table, _, prefix = item.partition("|")
            subprocess.run(["ip", "route", "del", "table", table, prefix],
                           capture_output=True, text=True, timeout=10)
        os.makedirs(self.base_dir, exist_ok=True)
        with open(state_path, "w", encoding="utf-8") as f:
            json.dump(wanted, f)
        return notes

    def _apply_mtr(self, old, new):
        old_t = (old.get("service") or {}).get("mtr") or {}
        new_t = (new.get("service") or {}).get("mtr") or {}
        if old_t == new_t:
            return []
        import shlex
        import signal
        run_dir = os.path.join(self.base_dir, "run")
        mtr_dir = os.path.join(self.base_dir, "mtr")
        os.makedirs(run_dir, exist_ok=True)
        os.makedirs(mtr_dir, exist_ok=True)

        def pid_path(name):
            return os.path.join(run_dir, f"mtr-{name}.pid")

        def stop(name):
            pid = None
            try:
                with open(pid_path(name), encoding="utf-8") as f:
                    pid = int(f.read().strip())
            except (OSError, ValueError):
                pass
            if pid:
                try:
                    os.killpg(pid, signal.SIGTERM)
                except OSError:
                    try:
                        os.kill(pid, signal.SIGTERM)
                    except OSError:
                        pass
            try:
                os.remove(pid_path(name))
            except OSError:
                pass

        notes = []
        for name in set(old_t) - set(new_t):
            stop(name)
            notes.append(f"mtr {name}: removed")
        for name, cfg in new_t.items():
            if not isinstance(cfg, dict):
                continue
            if old_t.get(name) == cfg:
                continue
            stop(name)
            if cfg.get("disable") or not cfg.get("target"):
                notes.append(f"mtr {name}: stopped")
                continue
            count = max(1, int(cfg.get("count") or 10))
            interval = max(10, int(cfg.get("interval") or 60))
            cmd = ["mtr", "-r", "-n", "-c", str(count), "-i", "1"]
            if cfg.get("interface"):
                cmd += ["-I", str(cfg["interface"])]
            if cfg.get("max-hops"):
                cmd += ["-m", str(cfg["max-hops"])]
            cmd.append(str(cfg["target"]))
            log = os.path.join(mtr_dir, f"{name}.log")
            run_cmd = " ".join(shlex.quote(x) for x in cmd)
            script = (f"while true; do {run_cmd} >> {shlex.quote(log)} 2>&1; "
                      f"echo >> {shlex.quote(log)}; sleep {interval}; done")
            proc = subprocess.Popen(["/bin/sh", "-c", script],
                                    stdout=subprocess.DEVNULL,
                                    stderr=subprocess.DEVNULL,
                                    start_new_session=True)
            with open(pid_path(name), "w", encoding="utf-8") as f:
                f.write(str(proc.pid))
            notes.append(f"mtr {name}: started pid {proc.pid} "
                         f"({count} probes every {interval}s)")
        return notes

    def _apply_tcp_mss(self, old, new):
        def mss_map(cfg):
            found = {}
            for items in (cfg.get("interfaces") or {}).values():
                if not isinstance(items, dict):
                    continue
                for name, body in items.items():
                    if isinstance(body, dict) and body.get("tcp-mss"):
                        found[name] = int(body["tcp-mss"])
            return found

        old_m = mss_map(old)
        new_m = mss_map(new)
        if old_m == new_m:
            return []
        native = (os.path.isdir("/etc/nftables.d")
                  and os.access("/etc/nftables.d", os.W_OK))
        include_dir = "/etc/nftables.d" if native else self.base_dir
        path = os.path.join(include_dir, "20-vyos-mss.nft")
        # Drop the legacy standalone table if a previous version made one.
        try:
            subprocess.run(["nft", "delete", "table", "inet", "vyos_mss"],
                           capture_output=True, text=True, timeout=10)
        except (OSError, subprocess.SubprocessError):
            pass
        if not new_m:
            try:
                os.remove(path)
            except OSError:
                pass
            if native:
                subprocess.run(["fw4", "restart"], capture_output=True,
                               text=True, timeout=60)
            return ["tcp-mss: removed"]
        lines = ["chain vyos_mss_forward {",
                 "    type filter hook forward priority mangle; policy accept;"]
        for name, mss in sorted(new_m.items()):
            lines.append(f'    oifname "{name}" tcp flags & (syn|rst) == syn '
                         f"tcp option maxseg size set {mss}")
            lines.append(f'    iifname "{name}" tcp flags & (syn|rst) == syn '
                         f"tcp option maxseg size set {mss}")
        lines += ["}", "chain vyos_mss_output {",
                  "    type filter hook output priority mangle; policy accept;"]
        for name, mss in sorted(new_m.items()):
            lines.append(f'    oifname "{name}" tcp flags & (syn|rst) == syn '
                         f"tcp option maxseg size set {mss}")
        lines.append("}")
        text = "\n".join(lines) + "\n"
        os.makedirs(include_dir, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
        if native:
            proc = subprocess.run(["fw4", "reload"], capture_output=True,
                                  text=True, timeout=60)
            if proc.returncode != 0:
                return [f"tcp-mss: fw4 reload failed: "
                        f"{(proc.stderr or '').strip()[:160]}"]
        return [f"tcp-mss: {len(new_m)} interface(s) via fw4 include"]

    def _apply_wan_lb(self, old, new):
        old_w = (old.get("load-balancing") or {}).get("wan") or {}
        new_w = (new.get("load-balancing") or {}).get("wan") or {}
        if old_w == new_w:
            return []
        if not os.path.exists("/etc/init.d/mwan3"):
            return ["wan-lb: mwan3 is not installed; nothing applied"]
        backup = os.path.join(self.base_dir, "backup", "mwan3.orig")
        os.makedirs(os.path.dirname(backup), exist_ok=True)
        if os.path.exists("/etc/config/mwan3") and not os.path.exists(backup):
            shutil.copy2("/etc/config/mwan3", backup)
        try:
            out = self._uci("show", "mwan3").stdout
            for line in out.splitlines():
                if line.startswith("mwan3.vyos_wan_"):
                    sec = line.split(".")[1].split("=")[0]
                    try:
                        self._uci("delete", f"mwan3.{sec}")
                    except subprocess.CalledProcessError:
                        pass
            if not new_w:
                if os.path.exists(backup):
                    shutil.copy2(backup, "/etc/config/mwan3")
                subprocess.run(["/etc/init.d/mwan3", "stop"],
                               capture_output=True, text=True, timeout=20)
                return ["wan-lb: stopped"]
            def logical_name(ifname):
                if self._uci_get(f"network.{ifname}") is not None:
                    return str(ifname)
                try:
                    out = self._uci("show", "network").stdout
                except Exception:
                    out = ""
                for line in out.splitlines():
                    lhs, _, value = line.partition("=")
                    if (lhs.endswith(".device")
                            and value.strip("'\"") == str(ifname)):
                        return lhs.split(".")[1]
                return str(ifname)

            interfaces = new_w.get("interface") or {}
            members = []
            for index, (ifname, cfg) in enumerate(sorted(interfaces.items())):
                cfg = cfg if isinstance(cfg, dict) else {}
                logical = logical_name(ifname)
                sec = logical
                self._uci("set", f"mwan3.{sec}=interface")
                self._uci("set", f"mwan3.{sec}.enabled=1")
                self._uci("set", f"mwan3.{sec}.family=ipv4")
                self._uci("set", f"mwan3.{sec}.track_ip="
                          f"{cfg.get('track-ip') or '1.1.1.1'}")
                self._uci("set", f"mwan3.{sec}.track_method=ping")
                self._uci("set", f"mwan3.{sec}.reliability=1")
                self._uci("set", f"mwan3.{sec}.count=1")
                self._uci("set", f"mwan3.{sec}.timeout=3")
                self._uci("set", f"mwan3.{sec}.interval=5")
                self._uci("set", f"mwan3.{sec}.down=3")
                self._uci("set", f"mwan3.{sec}.up=5")
                member = f"vyos_wan_m_{index}"
                self._uci("set", f"mwan3.{member}=member")
                self._uci("set", f"mwan3.{member}.interface={logical}")
                self._uci("set", f"mwan3.{member}.metric={index + 1}")
                self._uci("set", f"mwan3.{member}.weight="
                          f"{cfg.get('weight') or 1}")
                members.append(member)
            policy = "vyos_wan_policy"
            self._uci("set", f"mwan3.{policy}=policy")
            for member in members:
                self._uci("add_list", f"mwan3.{policy}.use_member={member}")
            rule = "vyos_wan_rule"
            self._uci("set", f"mwan3.{rule}=rule")
            self._uci("set", f"mwan3.{rule}.dest_ip=0.0.0.0/0")
            self._uci("set", f"mwan3.{rule}.proto=all")
            self._uci("set", f"mwan3.{rule}.use_policy={policy}")
            self._uci("commit", "mwan3")
            subprocess.run(["/etc/init.d/mwan3", "restart"],
                           capture_output=True, text=True, timeout=30)
            return [f"wan-lb: {len(members)} interface(s) via mwan3"]
        except Exception as e:  # noqa: BLE001
            return [f"wan-lb apply failed: {e}"]

    def _apply_haproxy(self, old, new):
        old_lb = (old.get("load-balancing") or {}).get("haproxy") or {}
        new_lb = (new.get("load-balancing") or {}).get("haproxy") or {}
        if old_lb == new_lb:
            return []
        cfg_path = ("/etc/haproxy.cfg" if os.path.isdir("/etc")
                    else os.path.join(self.base_dir, "haproxy.cfg"))
        backup = os.path.join(self.base_dir, "backup", "haproxy.cfg.orig")
        os.makedirs(os.path.dirname(backup), exist_ok=True)
        if os.path.exists(cfg_path) and not os.path.exists(backup):
            shutil.copy2(cfg_path, backup)
        services = new_lb.get("service") or {}
        if not services:
            try:
                subprocess.run(["/etc/init.d/haproxy", "stop"],
                               capture_output=True, text=True, timeout=15)
            except (OSError, subprocess.SubprocessError):
                pass
            if os.path.exists(backup):
                shutil.copy2(backup, cfg_path)
            return ["haproxy: stopped"]
        text = render_haproxy_cfg(new_lb)
        with open(cfg_path, "w", encoding="utf-8") as f:
            f.write(text)
        os.chmod(cfg_path, 0o600)
        try:
            check = subprocess.run(["haproxy", "-c", "-q", "-f", cfg_path],
                                   capture_output=True, text=True, timeout=15)
        except (OSError, subprocess.SubprocessError) as e:
            return [f"haproxy: validation unavailable ({e})"]
        if check.returncode != 0:
            if os.path.exists(backup):
                shutil.copy2(backup, cfg_path)
            return [f"haproxy: invalid config: {(check.stderr or '').strip()[:200]}"]
        subprocess.run(["/etc/init.d/haproxy", "restart"],
                       capture_output=True, text=True, timeout=20)
        return [f"haproxy: {len(services)} service(s)"]

    def _apply_qos(self, old, new):
        old_q = old.get("qos") or {}
        new_q = new.get("qos") or {}
        if old_q == new_q:
            return []
        notes: List[str] = []
        for gone in set((old_q.get("interface") or {})) - set(
                (new_q.get("interface") or {})):
            for args in (["qdisc", "del", "dev", str(gone), "root"],
                         ["qdisc", "del", "dev", str(gone), "ingress"]):
                try:
                    subprocess.run(["tc"] + args, capture_output=True,
                                   text=True, timeout=10)
                except (OSError, subprocess.SubprocessError):
                    pass
        failed = 0
        for cmd in render_qos_commands(new_q):
            try:
                proc = subprocess.run(cmd, capture_output=True, text=True,
                                      timeout=15)
                if proc.returncode != 0:
                    failed += 1
            except (OSError, subprocess.SubprocessError):
                failed += 1
        count = len(render_qos_commands(new_q))
        notes.append(f"qos: applied {count - failed}/{count} tc command(s)")
        return notes

    def _apply_flow_accounting(self, old, new):
        old_fa = (old.get("system") or {}).get("flow-accounting") or {}
        new_fa = (new.get("system") or {}).get("flow-accounting") or {}
        if old_fa == new_fa:
            return []
        notes: List[str] = []
        try:
            out = self._uci("show", "softflowd").stdout
            for line in out.splitlines():
                if line.startswith("softflowd.vyos_fa_"):
                    sec = line.split(".")[1].split("=")[0]
                    try:
                        self._uci("delete", f"softflowd.{sec}")
                    except subprocess.CalledProcessError:
                        pass
            interfaces = _as_list(new_fa.get("interface"))
            servers = (new_fa.get("netflow") or {}).get("server") or {}
            host_port = None
            version = 9
            if servers:
                ip = sorted(servers)[0]
                cfg = servers[ip] or {}
                host_port = f"{ip}:{cfg.get('port') or 2055}"
                version = cfg.get("version") or 9
            if (new_fa.get("sflow") or {}).get("server"):
                notes.append("flow-accounting: sFlow is not supported by "
                             "softflowd, use netflow")
            if interfaces and host_port:
                for i, ifname in enumerate(interfaces):
                    sec = f"vyos_fa_{i}"
                    self._uci("set", f"softflowd.{sec}=softflowd")
                    self._uci("set", f"softflowd.{sec}.enabled=1")
                    self._uci("set", f"softflowd.{sec}.interface={ifname}")
                    self._uci("set", f"softflowd.{sec}.host_port={host_port}")
                    self._uci("set", f"softflowd.{sec}.export_version={version}")
                    self._uci("set", f"softflowd.{sec}.pid_file="
                              f"/var/run/vyoscli-softflowd-{i}.pid")
                notes.append(f"flow-accounting: {len(interfaces)} interface(s) "
                             f"-> {host_port}")
            else:
                notes.append("flow-accounting: need interface and netflow "
                             "server, nothing started")
            self._uci("commit", "softflowd")
            subprocess.run(["/etc/init.d/softflowd", "restart"],
                           capture_output=True, text=True, timeout=15)
        except Exception as e:  # noqa: BLE001
            notes.append(f"flow-accounting apply failed: {e}")
        return notes

    def _apply_pki(self, old, new):
        old_p = old.get("pki") or {}
        new_p = new.get("pki") or {}
        if old_p == new_p:
            return []
        base = os.path.join(self.base_dir, "pki")
        os.makedirs(base, exist_ok=True)
        notes: List[str] = []
        written = 0

        def write_file(path: str, content, mode: int) -> None:
            nonlocal written
            if not content:
                return
            text = _format_pem(content)
            with open(path, "w", encoding="utf-8") as f:
                f.write(text)
            os.chmod(path, mode)
            written += 1

        def kind_dir(kind: str) -> str:
            path = os.path.join(base, kind)
            os.makedirs(path, exist_ok=True)
            return path

        for name, cfg in (new_p.get("ca") or {}).items():
            if not isinstance(cfg, dict):
                continue
            d = kind_dir("ca")
            write_file(os.path.join(d, f"{name}.crt"), cfg.get("certificate"),
                       0o644)
            write_file(os.path.join(d, f"{name}.crl"), cfg.get("crl"), 0o644)
            write_file(os.path.join(d, f"{name}.key"),
                       (cfg.get("private") or {}).get("key"), 0o600)
        for name, cfg in (new_p.get("certificate") or {}).items():
            if not isinstance(cfg, dict):
                continue
            d = kind_dir("certificate")
            write_file(os.path.join(d, f"{name}.crt"), cfg.get("certificate"),
                       0o644)
            write_file(os.path.join(d, f"{name}.key"),
                       (cfg.get("private") or {}).get("key"), 0o600)
        for name, cfg in (new_p.get("key-pair") or {}).items():
            if not isinstance(cfg, dict):
                continue
            d = kind_dir("key-pair")
            write_file(os.path.join(d, f"{name}.key"),
                       (cfg.get("private") or {}).get("key"), 0o600)
            write_file(os.path.join(d, f"{name}.pub"),
                       (cfg.get("public") or {}).get("key"), 0o644)
        for name in (new_p.get("dh") or {}):
            write_file(os.path.join(kind_dir("dh"), f"{name}.pem"),
                       "# placeholder: upload DH parameters via certificate",
                       0o600)
        # Remove files whose names disappeared.
        for kind, exts in (("ca", (".crt", ".crl", ".key")),
                           ("certificate", (".crt", ".key")),
                           ("key-pair", (".key", ".pub")),
                           ("dh", (".pem",))):
            current = set((new_p.get(kind) or {}))
            directory = os.path.join(base, kind)
            try:
                entries = os.listdir(directory)
            except OSError:
                continue
            for entry in entries:
                stem, dot, ext = entry.partition(".")
                if dot and f".{ext}" in exts and stem not in current:
                    try:
                        os.remove(os.path.join(directory, entry))
                    except OSError:
                        pass
        if written:
            notes.append(f"pki: wrote {written} file(s) under {base}")
        return notes

    def _apply_l2tp(self, old, new):
        old_v = (old.get("vpn") or {}).get("l2tp") or {}
        new_v = (new.get("vpn") or {}).get("l2tp") or {}
        if old_v == new_v:
            return []
        backup = os.path.join(self.base_dir, "backup", "l2tp")
        os.makedirs(backup, exist_ok=True)
        etc = (os.environ.get("VYOSCLI_ETC_ROOT")
               or ("/etc" if os.access("/etc", os.W_OK) else self.base_dir))
        files = {
            "conf": os.path.join(etc, "xl2tpd", "xl2tpd.conf"),
            "options": os.path.join(etc, "ppp", "options.xl2tpd"),
            "chap": os.path.join(etc, "ppp", "chap-secrets"),
        }
        os.makedirs(os.path.join(etc, "xl2tpd"), exist_ok=True)
        os.makedirs(os.path.join(etc, "ppp"), exist_ok=True)
        for key, path in files.items():
            saved = os.path.join(backup, os.path.basename(path) + ".orig")
            if os.path.exists(path) and not os.path.exists(saved):
                shutil.copy2(path, saved)
        notes: List[str] = []
        try:
            if not new_v:
                for key, path in files.items():
                    saved = os.path.join(backup,
                                         os.path.basename(path) + ".orig")
                    if os.path.exists(saved):
                        shutil.copy2(saved, path)
                subprocess.run(["/etc/init.d/xl2tpd", "stop"],
                               capture_output=True, text=True, timeout=20)
                return ["l2tp: disabled, original config restored"]
            port = new_v.get("port") or 1701
            local_ip = new_v.get("local-ip") or "10.90.0.1"
            start = new_v.get("pool-start") or "10.90.0.100"
            end = new_v.get("pool-end") or "10.90.0.200"
            dns = new_v.get("name-server") or "8.8.8.8"
            conf = [
                "[global]",
                f"port = {port}",
                "auth file = /etc/xl2tpd/xl2tp-secrets",
                "access control = no",
                "",
                "[lns default]",
                f"ip range = {start}-{end}",
                f"local ip = {local_ip}",
                "require authentication = yes",
                "refuse pap = yes",
                "require chap = yes",
                "name = l2tpd",
                "pppoptfile = /etc/ppp/options.xl2tpd",
                "length bit = yes",
            ]
            with open(files["conf"], "w", encoding="utf-8") as f:
                f.write("\n".join(conf) + "\n")
            options = [
                "require-mschap-v2",
                f"ms-dns {dns}",
                "asyncmap 0",
                "auth",
                "lock",
                "hide-password",
                "modem",
                "name l2tpd",
                "proxyarp",
                "lcp-echo-interval 30",
                "lcp-echo-failure 4",
            ]
            with open(files["options"], "w", encoding="utf-8") as f:
                f.write("\n".join(options) + "\n")
            users = new_v.get("user") or {}
            chap = ["# managed by vyoscli"]
            for username, cfg in users.items():
                if isinstance(cfg, dict):
                    chap.append(f"{username} l2tpd {cfg.get('password') or ''} *")
            with open(files["chap"], "w", encoding="utf-8") as f:
                f.write("\n".join(chap) + "\n")
            os.chmod(files["chap"], 0o600)
            os.chmod(files["options"], 0o600)
            subprocess.run(["/etc/init.d/xl2tpd", "restart"],
                           capture_output=True, text=True, timeout=20)
            notes.append(f"l2tp: port {port}, pool {start}-{end}, "
                         f"{len(users)} user(s)")
        except Exception as e:  # noqa: BLE001
            notes.append(f"l2tp apply failed: {e}")
        return notes

    def _apply_dhcp_relay(self, old, new):
        old_r = (old.get("service") or {}).get("dhcp-relay") or {}
        new_r = (new.get("service") or {}).get("dhcp-relay") or {}
        if old_r == new_r:
            return []
        etc_root = (os.environ.get("VYOSCLI_ETC_ROOT")
                    or ("/etc" if os.access("/etc", os.W_OK)
                        else self.base_dir))
        os.makedirs(etc_root, exist_ok=True)
        conf = os.path.join(etc_root, "dhcp-fwd.conf")
        backup = os.path.join(self.base_dir, "backup", "dhcp-fwd.conf.orig")
        os.makedirs(os.path.dirname(backup), exist_ok=True)
        if os.path.exists(conf) and not os.path.exists(backup):
            shutil.copy2(conf, backup)
        run_dir = (os.environ.get("VYOSCLI_RUN_DIR")
                   or ("/var/run" if os.access("/var/run", os.W_OK)
                       else os.path.join(self.base_dir, "run")))
        os.makedirs(run_dir, exist_ok=True)
        pidfile = os.path.join(run_dir, "dhcp-fwd.pid")

        def stop():
            try:
                with open(pidfile, encoding="utf-8") as f:
                    pid = int(f.read().strip())
                os.kill(pid, 15)
            except (OSError, ValueError):
                pass
            for path in (pidfile,):
                try:
                    os.remove(path)
                except OSError:
                    pass

        stop()
        if not new_r:
            if os.path.exists(backup):
                shutil.copy2(backup, conf)
            return ["dhcp-relay: stopped"]
        servers = _as_list(new_r.get("server"))
        interfaces = _as_list(new_r.get("interface"))
        upstreams = _as_list(new_r.get("upstream-interface"))
        if not servers or not interfaces or not upstreams:
            return ["dhcp-relay: need server, interface and upstream-interface"]
        var_lib = os.environ.get("VYOSCLI_VAR_LIB", "/var/lib")
        chroot_dir = os.path.join(var_lib, "dhcp-fwd")
        os.makedirs(chroot_dir, exist_ok=True)
        lines = [
            "user dhcp-fwd",
            "group dhcp-fwd",
            f"chroot {chroot_dir}",
            "logfile /var/log/dhcp-fwd.log",
            "pidfile " + pidfile,
            "",
        ]
        for ifname in interfaces:
            lines.append(f"if {ifname} true false true")
        for ifname in upstreams:
            lines.append(f"if {ifname} false true true")
        lines.append("")
        for server in servers:
            lines.append(f"server ip {server}")
        with open(conf, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
        try:
            proc = subprocess.run(["dhcp-fwd", "-c", conf],
                                  capture_output=True, text=True, timeout=10)
        except (OSError, subprocess.SubprocessError) as e:
            return [f"dhcp-relay: start failed ({e})"]
        if proc.returncode != 0:
            return [f"dhcp-relay: start failed: "
                    f"{(proc.stderr or '').strip()[:160]}"]
        return [f"dhcp-relay: {len(servers)} server(s), "
                f"{len(interfaces)} client iface(s)"]

    def _apply_openconnect(self, old, new):
        old_v = (old.get("vpn") or {}).get("openconnect") or {}
        new_v = (new.get("vpn") or {}).get("openconnect") or {}
        if old_v == new_v:
            return []
        notes: List[str] = []
        try:
            out = self._uci("show", "ocserv").stdout
            for line in out.splitlines():
                if line.startswith("ocserv.vyos_oc_"):
                    sec = line.split(".")[1].split("=")[0]
                    try:
                        self._uci("delete", f"ocserv.{sec}")
                    except subprocess.CalledProcessError:
                        pass
            if not new_v:
                self._uci("set", "ocserv.config.enable=0")
                self._uci("commit", "ocserv")
                subprocess.run(["/etc/init.d/ocserv", "stop"],
                               capture_output=True, text=True, timeout=30)
                return ["openconnect: disabled"]
            self._uci("set", "ocserv.config=ocserv")
            self._uci("set", "ocserv.config.enable=1")
            self._uci("set", f"ocserv.config.port={new_v.get('port') or 4443}")
            self._uci("set", "ocserv.config.auth=plain")
            network = new_v.get("network")
            if network:
                net = ipaddress.ip_network(str(network), strict=False)
                self._uci("set", f"ocserv.config.ipaddr={net.network_address}")
                self._uci("set", f"ocserv.config.netmask={net.netmask}")
            if new_v.get("max-clients"):
                self._uci("set",
                          f"ocserv.config.max_clients={new_v['max-clients']}")
            if new_v.get("dpd"):
                self._uci("set", f"ocserv.config.dpd={new_v['dpd']}")
            users = new_v.get("user") or {}
            for username, cfg in users.items():
                if not isinstance(cfg, dict):
                    continue
                sec = "vyos_oc_" + re.sub(r"[^A-Za-z0-9_]", "_", str(username))
                self._uci("set", f"ocserv.{sec}=ocservusers")
                self._uci("set", f"ocserv.{sec}.name={username}")
                self._uci("set", f"ocserv.{sec}.group={cfg.get('group') or '*'}")
                self._uci("set", f"ocserv.{sec}.password={cfg.get('password') or ''}")
            self._uci("commit", "ocserv")
            try:
                os.chmod("/etc/config/ocserv", 0o600)
            except OSError:
                pass
            subprocess.run(["/etc/init.d/ocserv", "restart"],
                           capture_output=True, text=True, timeout=30)
            notes.append(f"openconnect: port {new_v.get('port') or 4443}, "
                         f"{len(users)} user(s)")
        except Exception as e:  # noqa: BLE001
            notes.append(f"openconnect apply failed: {e}")
        return notes

    def _apply_vrrp(self, old, new):
        old_ha = old.get("high-availability") or {}
        new_ha = new.get("high-availability") or {}
        if old_ha == new_ha:
            return []
        notes: List[str] = []
        try:
            out = self._uci("show", "keepalived").stdout
            for line in out.splitlines():
                if line.startswith("keepalived.vyos_ha_"):
                    sec = line.split(".")[1].split("=")[0]
                    try:
                        self._uci("delete", f"keepalived.{sec}")
                    except subprocess.CalledProcessError:
                        pass
            vrrp = new_ha.get("vrrp") or {}
            startup = (vrrp.get("global-parameters") or {}).get("startup-delay")
            if startup:
                self._uci("set", "keepalived.globals=globals")
                self._uci("set",
                          f"keepalived.globals.vrrp_startup_delay={startup}")
            groups = vrrp.get("group") or {}
            for name, cfg in groups.items():
                if not isinstance(cfg, dict):
                    continue
                sec = "vyos_ha_" + re.sub(r"[^A-Za-z0-9_]", "_", str(name))
                self._uci("set", f"keepalived.{sec}=vrrp_instance")
                self._uci("set", f"keepalived.{sec}.name={name}")
                if cfg.get("interface"):
                    self._uci("set", f"keepalived.{sec}.interface={cfg['interface']}")
                if cfg.get("vrid"):
                    self._uci("set",
                              f"keepalived.{sec}.virtual_router_id={cfg['vrid']}")
                if cfg.get("priority"):
                    self._uci("set", f"keepalived.{sec}.priority={cfg['priority']}")
                if cfg.get("no-preempt"):
                    self._uci("set", f"keepalived.{sec}.nopreempt=1")
                if cfg.get("preempt-delay"):
                    self._uci("set",
                              f"keepalived.{sec}.preempt_delay={cfg['preempt-delay']}")
                if cfg.get("hello-source-address"):
                    self._uci("set", f"keepalived.{sec}.unicast_src_ip="
                              f"{cfg['hello-source-address']}")
                for i, addr in enumerate(_as_list(cfg.get("address"))):
                    vip = f"{sec}_vip_{i}"
                    self._uci("set", f"keepalived.{vip}=ipaddress")
                    self._uci("set", f"keepalived.{vip}.name={vip}")
                    self._uci("set", f"keepalived.{vip}.address={addr}")
                    if cfg.get("interface"):
                        self._uci("set",
                                  f"keepalived.{vip}.device={cfg['interface']}")
                    self._uci("add_list",
                              f"keepalived.{sec}.virtual_ipaddress={vip}")
                for i, ifname in enumerate(_as_list(
                        (cfg.get("track") or {}).get("interface"))):
                    tsec = f"{sec}_track_{i}"
                    self._uci("set", f"keepalived.{tsec}=track_interface")
                    self._uci("set", f"keepalived.{tsec}.name={ifname}")
                    self._uci("add_list",
                              f"keepalived.{sec}.track_interface={ifname}")
                for i, peer in enumerate(_as_list(cfg.get("peer-address"))):
                    psec = f"{sec}_peer_{i}"
                    self._uci("set", f"keepalived.{psec}=peer")
                    self._uci("set", f"keepalived.{psec}.name={psec}")
                    self._uci("set", f"keepalived.{psec}.address={peer}")
                    self._uci("add_list",
                              f"keepalived.{sec}.unicast_peer={psec}")
            for name, cfg in (vrrp.get("sync-group") or {}).items():
                if not isinstance(cfg, dict):
                    continue
                sec = "vyos_ha_sync_" + re.sub(r"[^A-Za-z0-9_]", "_", str(name))
                self._uci("set", f"keepalived.{sec}=vrrp_sync_group")
                self._uci("set", f"keepalived.{sec}.name={name}")
                for member in _as_list(cfg.get("member")):
                    self._uci("add_list", f"keepalived.{sec}.group={member}")
            self._uci("commit", "keepalived")
            subprocess.run(["/etc/init.d/keepalived", "restart"],
                           capture_output=True, text=True, timeout=20)
            notes.append(f"vrrp: {len(groups)} group(s)")
        except Exception as e:  # noqa: BLE001
            notes.append(f"vrrp apply failed: {e}")
        return notes

    def _apply_macsec(self, old, new):
        old_if = old.get("interfaces") or {}
        new_if = new.get("interfaces") or {}
        old_m = old_if.get("macsec") or {}
        new_m = new_if.get("macsec") or {}
        if old_m == new_m:
            return []
        notes: List[str] = []

        def run(args):
            try:
                return subprocess.run(["ip"] + args, capture_output=True,
                                      text=True, timeout=10)
            except (OSError, subprocess.SubprocessError):
                return None

        for gone in set(old_m) - set(new_m):
            run(["link", "del", str(gone)])
            notes.append(f"macsec: removed {gone}")
        for name, cfg in new_m.items():
            if not isinstance(cfg, dict):
                continue
            source = cfg.get("source-interface")
            if not source:
                notes.append(f"macsec: {name} needs source-interface")
                continue
            run(["link", "del", str(name)])
            args = ["link", "add", "link", str(source), str(name),
                    "type", "macsec"]
            if cfg.get("cipher"):
                args += ["cipher", str(cfg["cipher"])]
            proc = run(args)
            if proc is None or proc.returncode != 0:
                detail = (getattr(proc, "stderr", "") or "").strip()[:120]
                notes.append(f"macsec: {name} create failed: {detail}")
                continue
            if cfg.get("key"):
                run(["macsec", "add", str(name), "tx", "sa", "0", "pn", "1",
                     "on", "key", "00", str(cfg["key"])])
            if cfg.get("mtu"):
                run(["link", "set", str(name), "mtu", str(cfg["mtu"])])
            if cfg.get("address"):
                run(["addr", "replace", str(cfg["address"]), "dev", str(name)])
            run(["link", "set", str(name),
                 "down" if cfg.get("disable") else "up"])
            notes.append(f"macsec: configured {name} on {source}")
        return notes

    def _apply_bonding(self, old, new):
        old_if = old.get("interfaces") or {}
        new_if = new.get("interfaces") or {}
        old_b = old_if.get("bonding") or {}
        new_b = new_if.get("bonding") or {}
        if old_b == new_b:
            return []
        notes: List[str] = []

        def run(args):
            try:
                return subprocess.run(["ip"] + args, capture_output=True,
                                      text=True, timeout=10)
            except (OSError, subprocess.SubprocessError):
                return None

        for gone in set(old_b) - set(new_b):
            run(["link", "del", str(gone)])
            notes.append(f"bonding: removed {gone}")
        for name, cfg in new_b.items():
            if not isinstance(cfg, dict):
                continue
            run(["link", "del", str(name)])
            mode = str(cfg.get("mode") or "802.3ad")
            proc = run(["link", "add", str(name), "type", "bond", "mode", mode])
            if proc is None or proc.returncode != 0:
                detail = (getattr(proc, "stderr", "") or "").strip()[:120]
                notes.append(f"bonding: {name} create failed: {detail}")
                continue
            if cfg.get("hash-policy"):
                run(["link", "set", "dev", str(name), "type", "bond",
                     "xmit_hash_policy", str(cfg["hash-policy"])])
            for member in _as_list(cfg.get("member")):
                # Linux refuses to enslave an interface while it is up.
                run(["link", "set", "dev", str(member), "down"])
                proc = run(["link", "set", "dev", str(member),
                            "master", str(name)])
                if proc is None or proc.returncode != 0:
                    detail = (getattr(proc, "stderr", "") or "").strip()[:120]
                    notes.append(f"bonding: {member} enslave failed: {detail}")
                else:
                    notes.append(f"bonding: {member} -> {name}")
            if cfg.get("mtu"):
                run(["link", "set", str(name), "mtu", str(cfg["mtu"])])
            if cfg.get("address"):
                run(["addr", "replace", str(cfg["address"]), "dev", str(name)])
            run(["link", "set", str(name),
                 "down" if cfg.get("disable") else "up"])
            notes.append(f"bonding: configured {name} ({mode})")
        return notes

    def _apply_virtual_ifaces(self, old, new):
        old_if = old.get("interfaces") or {}
        new_if = new.get("interfaces") or {}
        notes: List[str] = []

        def run(args, ignore=True):
            try:
                proc = subprocess.run(["ip"] + args, capture_output=True,
                                      text=True, timeout=10)
            except (OSError, subprocess.SubprocessError) as e:
                return type("P", (), {"returncode": 1, "stderr": str(e)})()
            return proc

        changed = False
        for kind in ("vti", "geneve"):
            old_map = old_if.get(kind) or {}
            new_map = new_if.get(kind) or {}
            if old_map == new_map:
                continue
            changed = True
            for gone in set(old_map) - set(new_map):
                run(["link", "del", str(gone)])
                notes.append(f"{kind}: removed {gone}")
            for name, cfg in new_map.items():
                if not isinstance(cfg, dict):
                    continue
                run(["link", "del", str(name)])
                if kind == "vti":
                    if not (cfg.get("local-ip") and cfg.get("remote")):
                        notes.append(f"vti: {name} needs local-ip and remote")
                        continue
                    args = ["link", "add", str(name), "type", "vti",
                            "local", str(cfg["local-ip"]),
                            "remote", str(cfg["remote"])]
                    if cfg.get("key"):
                        args += ["key", str(cfg["key"])]
                else:
                    if not (cfg.get("remote") and cfg.get("vni")):
                        notes.append(f"geneve: {name} needs remote and vni")
                        continue
                    args = ["link", "add", str(name), "type", "geneve",
                            "id", str(cfg["vni"]),
                            "remote", str(cfg["remote"])]
                proc = run(args, ignore=False)
                if proc is None or proc.returncode != 0:
                    detail = (getattr(proc, "stderr", "") or "").strip()[:120]
                    notes.append(f"{kind}: {name} create failed: {detail}")
                    continue
                if cfg.get("mtu"):
                    run(["link", "set", str(name), "mtu", str(cfg["mtu"])])
                if cfg.get("address"):
                    run(["addr", "replace", str(cfg["address"]),
                         "dev", str(name)])
                run(["link", "set", str(name),
                     "down" if cfg.get("disable") else "up"])
                notes.append(f"{kind}: configured {name}")
        if changed:
            notes.append("virtual interfaces updated")
        return notes

    def _apply_pppoe(self, old, new):
        old_if = (old.get("interfaces") or {})
        new_if = (new.get("interfaces") or {})
        old_pp = old_if.get("pppoe") or {}
        new_pp = new_if.get("pppoe") or {}
        if old_pp == new_pp:
            return []
        notes: List[str] = []
        try:
            for gone in set(old_pp) - set(new_pp):
                section = re.sub(r"[^A-Za-z0-9_]", "_", str(gone))
                try:
                    self._uci("delete", f"network.{section}")
                except subprocess.CalledProcessError:
                    pass
                notes.append(f"pppoe: removed network.{section}")
            for ifname, cfg in new_pp.items():
                if not isinstance(cfg, dict):
                    continue
                section = re.sub(r"[^A-Za-z0-9_]", "_", str(ifname))
                source = cfg.get("source-interface")
                auth = cfg.get("authentication") or {}
                self._uci("set", f"network.{section}=interface")
                self._uci("set", f"network.{section}.proto=pppoe")
                if source:
                    self._uci("set", f"network.{section}.device={source}")
                if auth.get("username"):
                    self._uci("set", f"network.{section}.username={auth['username']}")
                if auth.get("password"):
                    self._uci("set", f"network.{section}.password={auth['password']}")
                if cfg.get("mtu"):
                    self._uci("set", f"network.{section}.mtu={cfg['mtu']}")
                if cfg.get("access-concentrator"):
                    self._uci("set",
                              f"network.{section}.ac={cfg['access-concentrator']}")
                if cfg.get("service-name"):
                    self._uci("set",
                              f"network.{section}.service={cfg['service-name']}")
                if cfg.get("no-peer-dns"):
                    self._uci("set", f"network.{section}.peerdns=0")
                if cfg.get("no-default-route"):
                    self._uci("set", f"network.{section}.defaultroute=0")
                if cfg.get("default-route-distance"):
                    self._uci("set", f"network.{section}.metric="
                              f"{cfg['default-route-distance']}")
                if cfg.get("disable"):
                    self._uci("set", f"network.{section}.auto=0")
                pppd = []
                if cfg.get("mru"):
                    pppd.append(f"mru {cfg['mru']}")
                if cfg.get("holdoff"):
                    pppd.append(f"holdoff {cfg['holdoff']}")
                if pppd:
                    self._uci("set", f"network.{section}.pppd_options="
                              f"'{' '.join(pppd)}'")
                notes.append(f"pppoe: configured network.{section}")
            self._uci("commit", "network")
            subprocess.run(["/etc/init.d/network", "reload"],
                           capture_output=True, text=True, timeout=15)
            notes.append("pppoe: netifd reloaded")
        except Exception as e:  # noqa: BLE001
            notes.append(f"pppoe apply failed: {e}")
        return notes

    def _apply_interfaces(self, old: Dict[str, Any], new: Dict[str, Any]) -> List[str]:
        old_if = old.get("interfaces") or {}
        new_if = new.get("interfaces") or {}
        if old_if == new_if:
            return []
        notes: List[str] = []
        mapping = self._network_map()
        eth = (new_if.get("ethernet") or {})
        for gone in set(old_if.get("ethernet") or {}) - set(eth):
            self._release_iface(gone, mapping, notes)
        old_eth = old_if.get("ethernet") or {}
        for ifname, cfg in eth.items():
            if not isinstance(cfg, dict) or ifname == "lo":
                continue
            sections = self._iface_sections(ifname)
            section = sections[0] if sections else None
            if cfg.get("mtu"):
                if section:
                    self._uci("set", f"network.{section}.mtu={cfg['mtu']}")
                    self._uci("commit", "network")
                subprocess.run(["ip", "link", "set", str(ifname), "mtu",
                                str(cfg["mtu"])], capture_output=True,
                               text=True, timeout=10)
            elif isinstance(old_eth.get(ifname), dict) and old_eth[ifname].get("mtu"):
                if section:
                    try:
                        self._uci("delete", f"network.{section}.mtu")
                        self._uci("commit", "network")
                    except subprocess.CalledProcessError:
                        pass
                subprocess.run(["ip", "link", "set", str(ifname), "mtu",
                                "1500"], capture_output=True, text=True,
                               timeout=10)
            addrs = _as_list(cfg.get("address"))
            # No address means "stop managing this port": restore a taken-over
            # section, or drop our own vyos_* interface.
            if not addrs:
                self._release_iface(ifname, mapping, notes)
                continue
            taken_over = False
            section = self._find_uci_section("network", "ifname", ifname)
            if section is None:
                owner = mapping.get(ifname)
                if owner is not None:
                    if not owner["direct"]:
                        notes.append(
                            f"{ifname}: is a port of network.{owner['section']} "
                            f"({owner['proto']}), configure the bridge instead")
                        continue
                    if (owner["proto"] or "").lower() not in ("static", "none", ""):
                        notes.append(
                            f"{ifname}: network.{owner['section']} uses proto "
                            f"'{owner['proto']}', refusing to replace it")
                        continue
                    # Static interface on this device: take it over instead of
                    # creating a second logical interface on the same port.
                    section = owner["section"]
                    self._backup_section(section)
                    taken_over = True
                    notes.append(f"{ifname}: applied to existing "
                                 f"network.{section}")
                else:
                    section = f"vyos_{ifname}"
                    self._uci("set", f"network.{section}=interface")
                    notes.append(f"uci: created network.{section} for {ifname}")
            if not taken_over:
                self._uci("set", f"network.{section}.ifname={ifname}")
            self._uci("set", f"network.{section}.proto=static")
            try:
                self._uci("delete", f"network.{section}.ipaddr")
            except subprocess.CalledProcessError:
                pass
            for addr in addrs:
                self._uci("add_list", f"network.{section}.ipaddr={addr}")
        # bridge + bridge-vlan (device section carries the ports; the interface
        # only references it — `type bridge` on an interface makes netifd
        # prepend "br-", and "br-vyos_br_<name>" exceeds IFNAMSIZ on real boxes)
        old_br = (old_if.get("bridge") or {})
        bridges = (new_if.get("bridge") or {})
        for gone in set(old_br) - set(bridges):
            for section in (f"vyos_br_{gone}", f"{gone}_dev"):
                try:
                    self._uci("delete", f"network.{section}")
                except subprocess.CalledProcessError:
                    pass
            # netifd does not remove devices it created once their config is
            # gone, so drop the kernel bridge ourselves.
            subprocess.run(["ip", "link", "del", gone],
                           capture_output=True, timeout=5)
        for brname, brcfg in bridges.items():
            if not isinstance(brcfg, dict):
                continue
            if len(brname) > 15:
                notes.append(f"bridge {brname}: name longer than 15 chars, "
                             f"netifd cannot create the device")
                continue
            dev_sec = f"{brname}_dev"
            iface_sec = f"vyos_br_{brname}"
            members = _as_list(brcfg.get("member") or brcfg.get("port"))
            if not members:
                notes.append(f"bridge {brname}: no member ports, netifd will "
                             f"not create the device")
            self._uci("set", f"network.{dev_sec}=device")
            self._uci("set", f"network.{dev_sec}.type=bridge")
            self._uci("set", f"network.{dev_sec}.name={brname}")
            if brcfg.get("vlan-aware") or brcfg.get("enable-vlan"):
                self._uci("set", f"network.{dev_sec}.vlan_filtering=1")
            try:
                self._uci("delete", f"network.{dev_sec}.ports")
            except subprocess.CalledProcessError:
                pass
            for port in members:
                self._uci("add_list", f"network.{dev_sec}.ports={port}")

            self._uci("set", f"network.{iface_sec}=interface")
            # Drop legacy options: `type=bridge` makes netifd rename the device.
            for legacy in ("type", "ports", "ifname"):
                try:
                    self._uci("delete", f"network.{iface_sec}.{legacy}")
                except subprocess.CalledProcessError:
                    pass
            self._uci("set", f"network.{iface_sec}.device={brname}")
            self._uci("set", f"network.{iface_sec}.proto=static")
            try:
                self._uci("delete", f"network.{iface_sec}.ipaddr")
            except subprocess.CalledProcessError:
                pass
            for addr in _as_list(brcfg.get("address")):
                self._uci("add_list", f"network.{iface_sec}.ipaddr={addr}")

            old_vlans = (old_br.get(brname) or {}).get("vlan") or {}
            for vid in set(old_vlans) - set(brcfg.get("vlan") or {}):
                try:
                    self._uci("delete", f"network.vyos_br_{brname}_vlan{vid}")
                except subprocess.CalledProcessError:
                    pass
            for vid, vcfg in (brcfg.get("vlan") or {}).items():
                if not isinstance(vcfg, dict):
                    continue
                vsec = f"vyos_br_{brname}_vlan{vid}"
                # Recreate from scratch: a stale ports list here is how the
                # "e:u* t:u* h:u* 1:u*" garbage ended up on a live box.
                try:
                    self._uci("delete", f"network.{vsec}")
                except subprocess.CalledProcessError:
                    pass
                self._uci("set", f"network.{vsec}=bridge-vlan")
                self._uci("set", f"network.{vsec}.device={brname}")
                self._uci("set", f"network.{vsec}.vlan={vid}")
                for p in _as_list(vcfg.get("untagged")):
                    self._uci("add_list", f"network.{vsec}.ports={p}:u*")
                for p in _as_list(vcfg.get("tagged")):
                    self._uci("add_list", f"network.{vsec}.ports={p}:t*")
        self._uci("commit", "network")
        try:
            subprocess.run(["/etc/init.d/network", "reload"],
                           capture_output=True, text=True, timeout=20)
            notes.append("netifd reloaded")
        except Exception as e:  # noqa: BLE001
            notes.append(f"network reload skipped: {e}")
        return notes

    def _apply_hostname(self, old: Dict[str, Any], new: Dict[str, Any]) -> List[str]:
        old_h = (old.get("system") or {}).get("host-name")
        new_h = (new.get("system") or {}).get("host-name")
        if old_h == new_h or not new_h:
            return []
        try:
            self._uci("set", "system.@system[0].hostname=" + str(new_h))
            self._uci("commit", "system")
            # `uci apply` only exists on newer releases (24.10+); on 23.05 the
            # system init script is what actually sets the kernel hostname.
            subprocess.run(["uci", "apply"], capture_output=True, timeout=10)
            subprocess.run(["/etc/init.d/system", "reload"],
                           capture_output=True, text=True, timeout=10)
            return [f"hostname -> {new_h}"]
        except Exception as e:  # noqa: BLE001
            return [f"hostname apply failed: {e}"]

    def _apply_name_servers(self, old: Dict[str, Any], new: Dict[str, Any]) -> List[str]:
        old_dns = _as_list((old.get("system") or {}).get("name-server"))
        new_dns = _as_list((new.get("system") or {}).get("name-server"))
        if old_dns == new_dns:
            return []
        notes = []
        try:
            try:
                self._uci("delete", "dhcp.@dnsmasq[0].server")
            except subprocess.CalledProcessError:
                pass
            for srv in new_dns:
                self._uci("add_list", f"dhcp.@dnsmasq[0].server={srv}")
            self._uci("commit", "dhcp")
            notes.append(f"dns servers -> {', '.join(map(str, new_dns))}")
            # domain-search
            new_search = _as_list((new.get("system") or {}).get("domain-search"))
            if new_search:
                try:
                    self._uci("set", f"dhcp.@dnsmasq[0].localuse=1")
                    self._uci("commit", "dhcp")
                except Exception:
                    pass
        except Exception as e:  # noqa: BLE001
            notes.append(f"dns apply failed: {e}")
        return notes

    def _apply_system_dns(self, old: Dict[str, Any], new: Dict[str, Any]) -> List[str]:
        old_dns = _as_list((old.get("system") or {}).get("dns"))
        new_dns = _as_list((new.get("system") or {}).get("dns"))
        if old_dns == new_dns:
            return []
        notes = []
        try:
            head_dir = "/tmp/resolv.conf.d"
            os.makedirs(head_dir, exist_ok=True)
            head = os.path.join(head_dir, "resolv.conf.head")
            with open(head, "w", encoding="utf-8") as f:
                for srv in new_dns:
                    f.write(f"nameserver {srv}\n")
            # reload resolv generator
            subprocess.run(["/etc/init.d/dnsmasq", "reload"],
                           capture_output=True, text=True, timeout=10)
            notes.append("system resolver -> "
                         + (", ".join(map(str, new_dns)) or "(cleared)"))
        except Exception as e:  # noqa: BLE001
            notes.append(f"system dns apply failed: {e}")
        return notes

    # Common IANA timezone name -> POSIX TZ string (glibc/busybox TZ env).
    TZ_POSIX = {
        "Asia/Shanghai": "CST-8",
        "Asia/Hong_Kong": "HKT-8",
        "Asia/Tokyo": "JST-9",
        "Asia/Singapore": "SGT-8",
        "UTC": "UTC0",
        "America/New_York": "EST5EDT",
        "America/Los_Angeles": "PST8PDT",
        "Europe/London": "GMT0BST,M3.5.0/1,M10.5.0",
    }

    def _apply_system_meta(self, old: Dict[str, Any], new: Dict[str, Any]) -> List[str]:
        old_s = old.get("system") or {}
        new_s = new.get("system") or {}
        notes = []
        try:
            # ---- timezone ----
            if old_s.get("timezone") != new_s.get("timezone"):
                tz = new_s.get("timezone", "UTC")
                self._uci("set", f"system.@system[0].zonename={tz}")
                posix = self.TZ_POSIX.get(tz, "UTC0")
                try:
                    with open("/etc/TZ", "w", encoding="utf-8") as f:
                        f.write(posix + "\n")
                except Exception:
                    pass
                os.environ["TZ"] = posix
                time.tzset()
                notes.append(f"timezone -> {tz}")
            # ---- ntp ----
            old_ntp = _as_list(old_s.get("ntp"))
            new_ntp = _as_list(new_s.get("ntp"))
            if old_ntp != new_ntp:
                try:
                    self._uci("get", "system.ntp")
                except subprocess.CalledProcessError:
                    # the whole section may have been removed by hand
                    self._uci("set", "system.ntp=timeserver")
                self._uci("set", "system.ntp.enabled=1")
                self._uci("set", "system.ntp.enable_server=0")
                try:
                    self._uci("delete", "system.ntp.server")
                except subprocess.CalledProcessError:
                    pass
                for srv in new_ntp:
                    self._uci("add_list", f"system.ntp.server={srv}")
                notes.append("ntp servers -> "
                             + ", ".join(map(str, new_ntp)))
            self._uci("commit", "system")
            subprocess.run(["/etc/init.d/sysntpd", "restart"],
                           capture_output=True, text=True, timeout=10)
        except Exception as e:  # noqa: BLE001
            notes.append(f"system meta apply failed: {e}")
        return notes

    def _apply_static_routes(self, old: Dict[str, Any], new: Dict[str, Any]) -> List[str]:
        old_routes = (old.get("protocols") or {}).get("static", {}).get("route") or {}
        new_routes = (new.get("protocols") or {}).get("static", {}).get("route") or {}
        if old_routes == new_routes:
            return []
        notes = []
        try:
            # Wipe out routes we previously created (sections named vyos_route_*)
            out = self._uci("show", "network").stdout
            for line in out.splitlines():
                if ".target=" in line and line.startswith("network.vyos_route_"):
                    section = line.split(".")[1]
                    self._uci("delete", f"network.{section}")
            # Create fresh sections for each route in candidate
            for prefix, cfg in new_routes.items():
                if not isinstance(cfg, dict):
                    continue
                # pick a deterministic section name from the prefix
                slug = prefix.replace("/", "_").replace(":", "_").replace(".", "_")
                section = f"vyos_route_{slug}"
                self._uci("set", f"network.{section}=route")
                self._uci("set", f"network.{section}.target={prefix}")
                if "next-hop" in cfg:
                    self._uci("set", f"network.{section}.gateway={cfg['next-hop']}")
                if "interface" in cfg:
                    self._uci("set", f"network.{section}.interface={cfg['interface']}")
                # blackhole / reject
                if cfg.get("blackhole"):
                    self._uci("set", f"network.{section}.type=blackhole")
                elif cfg.get("reject"):
                    self._uci("set", f"network.{section}.type=unreachable")
                # default interface: if only next-hop given, try eth0 (WAN)
                if "interface" not in cfg and not cfg.get("blackhole") and not cfg.get("reject"):
                    self._uci("set", "network." + section + ".interface=wan")
                notes.append(f"route {prefix} -> "
                             + (f"via {cfg.get('next-hop')}" if cfg.get("next-hop") else "")
                             + (f" dev {cfg.get('interface')}" if cfg.get("interface") else "")
                             + (" blackhole" if cfg.get("blackhole") else "")
                             + (" reject" if cfg.get("reject") else ""))
            self._uci("commit", "network")
            subprocess.run(["/etc/init.d/network", "reload"],
                           capture_output=True, text=True, timeout=20)
            notes.append("netifd reloaded")
        except Exception as e:  # noqa: BLE001
            notes.append(f"static route apply failed: {e}")
        return notes

    def _apply_snmp(self, old, new):
        old_s = (old.get("service") or {}).get("snmp") or {}
        new_s = (new.get("service") or {}).get("snmp") or {}
        if old_s == new_s:
            return []
        notes: List[str] = []
        try:
            out = self._uci("show", "snmpd").stdout
            for line in out.splitlines():
                if line.startswith("snmpd.vyos_snmp_"):
                    sec = line.split(".")[1].split("=")[0]
                    try:
                        self._uci("delete", f"snmpd.{sec}")
                    except subprocess.CalledProcessError:
                        pass
            self._uci("set", "snmpd.general=snmpd")
            self._uci("set", "snmpd.general.enabled=1")
            if new_s.get("contact") or new_s.get("location"):
                self._uci("set", "snmpd.system=system")
                if new_s.get("contact"):
                    self._uci("set", f"snmpd.system.sysContact={new_s['contact']}")
                if new_s.get("location"):
                    self._uci("set", f"snmpd.system.sysLocation={new_s['location']}")
            port = new_s.get("port") or 161
            addr = new_s.get("listen-address")
            self._uci("set", "snmpd.agent=agent")
            if addr and addr != "0.0.0.0":
                self._uci("set", f"snmpd.agent.agentaddress=UDP:{addr}:{port}")
            else:
                self._uci("set", f"snmpd.agent.agentaddress=UDP:{port}")
            communities = new_s.get("community") or {}
            for name, cfg in communities.items():
                if not isinstance(cfg, dict):
                    continue
                access = str(cfg.get("authorization") or "ro").lower()
                sec = f"vyos_snmp_{re.sub(r'[^A-Za-z0-9_]', '_', str(name))}"
                self._uci("set", f"snmpd.{sec}_com=com2sec")
                self._uci("set", f"snmpd.{sec}_com.secname={access}")
                self._uci("set", f"snmpd.{sec}_com.source=default")
                self._uci("set", f"snmpd.{sec}_com.community={name}")
                self._uci("set", f"snmpd.{sec}_com6=com2sec6")
                self._uci("set", f"snmpd.{sec}_com6.secname={access}")
                self._uci("set", f"snmpd.{sec}_com6.source=default")
                self._uci("set", f"snmpd.{sec}_com6.community={name}")
                for version in ("v1", "v2c", "usm"):
                    gsec = f"{sec}_{version}"
                    self._uci("set", f"snmpd.{gsec}=group")
                    self._uci("set", f"snmpd.{gsec}.group={name}")
                    self._uci("set", f"snmpd.{gsec}.version={version}")
                    self._uci("set", f"snmpd.{gsec}.secname={access}")
                asec = f"{sec}_access"
                self._uci("set", f"snmpd.{asec}=access")
                self._uci("set", f"snmpd.{asec}.group={name}")
                self._uci("set", f"snmpd.{asec}.context=none")
                self._uci("set", f"snmpd.{asec}.version=any")
                self._uci("set", f"snmpd.{asec}.level=noauth")
                self._uci("set", f"snmpd.{asec}.prefix=exact")
                self._uci("set", f"snmpd.{asec}.read=all")
                self._uci("set", f"snmpd.{asec}.write="
                          + ("all" if access == "rw" else "none"))
                self._uci("set", f"snmpd.{asec}.notify=none")
            self._uci("commit", "snmpd")
            subprocess.run(["/etc/init.d/snmpd", "restart"],
                           capture_output=True, text=True, timeout=15)
            notes.append(f"snmp: {len(communities)} community(ies) "
                         f"on UDP:{port}")
        except Exception as e:  # noqa: BLE001
            notes.append(f"snmp apply failed: {e}")
        return notes

    def _ra_backup_path(self, ifname: str) -> str:
        return os.path.join(self.base_dir, "backup", f"dhcp.{ifname}.json")

    def _backup_ra(self, ifname: str) -> None:
        path = self._ra_backup_path(ifname)
        if os.path.exists(path):
            return
        data = {}
        for key in ("ra", "dhcpv6", "ra_management", "ra_lifetime"):
            value = self._uci_get(f"dhcp.{ifname}.{key}")
            if value is not None:
                data[key] = value
        if data:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            self._dump(path, data)

    def _restore_ra(self, ifname: str, notes: List[str]) -> None:
        path = self._ra_backup_path(ifname)
        data = {}
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, ValueError):
            data = {}
        for key in ("ra", "dhcpv6", "ra_management", "ra_lifetime"):
            if data.get(key) is not None:
                self._uci("set", f"dhcp.{ifname}.{key}={data[key]}")
            else:
                try:
                    self._uci("delete", f"dhcp.{ifname}.{key}")
                except subprocess.CalledProcessError:
                    pass
        self._uci("commit", "dhcp")
        subprocess.run(["/etc/init.d/odhcpd", "restart"],
                       capture_output=True, text=True, timeout=15)
        try:
            os.remove(path)
        except OSError:
            pass
        notes.append(f"ra: restored dhcp.{ifname}")

    def _apply_router_advert(self, old, new):
        old_ra = (old.get("service") or {}).get("router-advert") or {}
        new_ra = (new.get("service") or {}).get("router-advert") or {}
        if old_ra == new_ra:
            return []
        notes: List[str] = []
        try:
            for gone in set(old_ra.get("interface") or {}) - set(
                    new_ra.get("interface") or {}):
                self._restore_ra(gone, notes)
            for ifname, cfg in (new_ra.get("interface") or {}).items():
                if not isinstance(cfg, dict):
                    continue
                self._backup_ra(ifname)
                self._uci("set", f"dhcp.{ifname}=dhcp")
                self._uci("set", f"dhcp.{ifname}.interface={ifname}")
                if cfg.get("no-send-advert"):
                    self._uci("set", f"dhcp.{ifname}.ra=disabled")
                else:
                    self._uci("set", f"dhcp.{ifname}.ra=server")
                    self._uci("set", f"dhcp.{ifname}.dhcpv6=server")
                if cfg.get("managed-flag"):
                    self._uci("set", f"dhcp.{ifname}.ra_management=1")
                if cfg.get("default-lifetime"):
                    self._uci("set", f"dhcp.{ifname}.ra_lifetime="
                              f"{cfg['default-lifetime']}")
                if cfg.get("prefix"):
                    notes.append(f"ra: {ifname} advertises prefixes from its "
                                 "interface addresses (explicit prefix stored "
                                 "but not programmed)")
            self._uci("commit", "dhcp")
            subprocess.run(["/etc/init.d/odhcpd", "restart"],
                           capture_output=True, text=True, timeout=15)
            notes.append(f"ra: {len(new_ra.get('interface') or {})} "
                         "interface(s)")
        except Exception as e:  # noqa: BLE001
            notes.append(f"router-advert apply failed: {e}")
        return notes

    def _apply_https(self, old, new):
        old_h = (old.get("service") or {}).get("https") or {}
        new_h = (new.get("service") or {}).get("https") or {}
        if old_h == new_h:
            return []
        pidfile = os.path.join(self.base_dir, "https.pid")
        try:
            with open(pidfile, encoding="utf-8") as f:
                old_pid = int(f.read().strip())
            os.kill(old_pid, 15)
        except (OSError, ValueError):
            pass
        try:
            os.remove(pidfile)
        except OSError:
            pass
        if not new_h or not new_h.get("port"):
            return ["https: stopped"] if old_h else []
        key = new_h.get("api-key")
        if not key:
            return ["https: api-key is required; server not started"]
        bind = new_h.get("listen-address") or "127.0.0.1"
        port = new_h["port"]
        store = os.path.join(self.base_dir, "running.json")
        argv = [sys.executable, "-m", "vyoscli.api",
                "--bind", str(bind), "--port", str(port),
                "--key", str(key), "--store", store]
        tls = ""
        cert_name = new_h.get("certificate")
        if cert_name:
            cert_dir = os.path.join(self.base_dir, "pki", "certificate")
            cert = os.path.join(cert_dir, f"{cert_name}.crt")
            tls_key = os.path.join(cert_dir, f"{cert_name}.key")
            if not (os.path.exists(cert) and os.path.exists(tls_key)):
                return [f"https: pki certificate {cert_name} not found; "
                        "server not started"]
            argv += ["--cert", cert, "--tls-key", tls_key]
            tls = " (TLS)"
        proc = subprocess.Popen(
            argv,
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL, start_new_session=True)
        time.sleep(0.3)
        if proc.poll() is not None:
            return ["https: API failed to start (check python3)"]
        with open(pidfile, "w", encoding="utf-8") as f:
            f.write(str(proc.pid))
        os.chmod(pidfile, 0o600)
        return [f"https: read-only API on {bind}:{port}{tls}"]

    def _apply_ntp(self, old, new):
        old_ntp = (old.get("service") or {}).get("ntp") or {}
        new_ntp = (new.get("service") or {}).get("ntp") or {}
        if old_ntp == new_ntp:
            return []
        servers = _as_list(new_ntp.get("server"))
        if not servers:
            return []
        notes: List[str] = []
        try:
            self._uci("set", "system.ntp.enabled=1")
            try:
                self._uci("delete", "system.ntp.server")
            except subprocess.CalledProcessError:
                pass
            for server in servers:
                self._uci("add_list", f"system.ntp.server={server}")
            self._uci("commit", "system")
            subprocess.run(["/etc/init.d/sysntpd", "restart"],
                           capture_output=True, text=True, timeout=15)
            notes.append(f"ntp: {len(servers)} server(s)")
            if new_ntp.get("listen-address"):
                notes.append("ntp: listen-address not supported by sysntpd")
        except Exception as e:  # noqa: BLE001
            notes.append(f"ntp apply failed: {e}")
        return notes

    def _apply_lldp(self, old, new):
        old_l = (old.get("service") or {}).get("lldp") or {}
        new_l = (new.get("service") or {}).get("lldp") or {}
        if old_l == new_l:
            return []
        notes: List[str] = []
        try:
            self._uci("set", "lldpd.config=config")
            try:
                self._uci("delete", "lldpd.config.interface")
            except subprocess.CalledProcessError:
                pass
            for ifname in _as_list(new_l.get("interface")):
                self._uci("add_list", f"lldpd.config.interface={ifname}")
            if new_l.get("description"):
                self._uci("set",
                          f"lldpd.config.lldp_description={new_l['description']}")
            self._uci("commit", "lldpd")
            subprocess.run(["/etc/init.d/lldpd", "restart"],
                           capture_output=True, text=True, timeout=15)
            notes.append(f"lldp: {len(_as_list(new_l.get('interface')))} "
                         "interface(s)")
        except Exception as e:  # noqa: BLE001
            notes.append(f"lldp apply failed: {e}")
        return notes

    def _apply_system_extra(self, old, new):
        old_sys = old.get("system") or {}
        new_sys = new.get("system") or {}
        keys = ("syslog", "conntrack", "sysctl", "watchdog")
        if all(old_sys.get(k) == new_sys.get(k) for k in keys):
            return []
        notes: List[str] = []
        syslog = new_sys.get("syslog") or {}
        if syslog:
            levels = {"emerg": 0, "alert": 1, "crit": 2, "err": 3, "error": 3,
                      "warning": 4, "warn": 4, "notice": 5, "info": 6,
                      "debug": 7, "all": 7}
            local = syslog.get("local") or {}
            console = syslog.get("console") or {}
            level = local.get("level") or console.get("level")
            uci_changed = False
            if level and str(level).lower() in levels:
                self._uci("set", "system.@system[0].conloglevel="
                          + str(levels[str(level).lower()]))
                uci_changed = True
            remotes = syslog.get("remote") or {}
            if remotes:
                host = sorted(remotes)[0]
                cfg = remotes[host] or {}
                self._uci("set", "system.@system[0].log_remote=1")
                self._uci("set", f"system.@system[0].log_ip={host}")
                if cfg.get("port"):
                    self._uci("set", f"system.@system[0].log_port={cfg['port']}")
                if cfg.get("protocol"):
                    self._uci("set", f"system.@system[0].log_proto={cfg['protocol']}")
                uci_changed = True
                if len(remotes) > 1:
                    notes.append("syslog: busybox logd supports one remote "
                                 f"server, using {host}")
            if uci_changed:
                self._uci("commit", "system")
                subprocess.run(["/etc/init.d/log", "restart"],
                               capture_output=True, text=True, timeout=15)
                notes.append("syslog: applied to logd")
            else:
                notes.append("syslog: options stored (no logd mapping)")
        conntrack = new_sys.get("conntrack") or {}
        sysctls = []
        if conntrack.get("table-size"):
            sysctls.append(("net.netfilter.nf_conntrack_max",
                            conntrack["table-size"]))
        timeouts = conntrack.get("timeout") or {}
        tcp = timeouts.get("tcp") or {}
        for key, sysname in (("established", "established"), ("close", "close"),
                             ("close-wait", "close_wait"),
                             ("fin-wait", "fin_wait"),
                             ("last-ack", "last_ack"),
                             ("syn-recv", "syn_recv"),
                             ("syn-sent", "syn_sent"),
                             ("time-wait", "time_wait")):
            if tcp.get(key):
                sysctls.append((f"net.netfilter.nf_conntrack_tcp_timeout_{sysname}",
                                tcp[key]))
        udp = timeouts.get("udp") or {}
        if udp.get("stream"):
            sysctls.append(("net.netfilter.nf_conntrack_udp_timeout_stream",
                            udp["stream"]))
        if udp.get("other"):
            sysctls.append(("net.netfilter.nf_conntrack_udp_timeout",
                            udp["other"]))
        icmp = (timeouts.get("icmp") or {}).get("timeout")
        if icmp:
            sysctls.append(("net.netfilter.nf_conntrack_icmp_timeout", icmp))
        generic = (timeouts.get("generic") or {}).get("timeout")
        if generic:
            sysctls.append(("net.netfilter.nf_conntrack_generic_timeout",
                            generic))
        sysctl_section = new_sys.get("sysctl") or {}
        params = (sysctl_section.get("parameter")
                  if isinstance(sysctl_section.get("parameter"), dict)
                  else sysctl_section)
        for key, cfg in params.items():
            if isinstance(cfg, dict) and cfg.get("value") is not None:
                sysctls.append((key, cfg["value"]))
        for key, value in sysctls:
            try:
                subprocess.run(["sysctl", "-w", f"{key}={value}"],
                               capture_output=True, text=True, timeout=5)
            except (OSError, subprocess.SubprocessError):
                pass
        if sysctls:
            path = os.path.join(self.base_dir, "sysctl.conf")
            try:
                with open(path, "w", encoding="utf-8") as f:
                    f.writelines(f"{k}={v}\n" for k, v in sysctls)
            except OSError:
                pass
            notes.append(f"system: applied {len(sysctls)} sysctl value(s)")
        watchdog = new_sys.get("watchdog") or {}
        if watchdog:
            module = watchdog.get("module")
            if module:
                try:
                    subprocess.run(["modprobe", str(module)],
                                   capture_output=True, text=True, timeout=10)
                except (OSError, subprocess.SubprocessError):
                    pass
            if os.path.exists("/dev/watchdog0") or os.path.exists("/dev/watchdog"):
                notes.append("watchdog: device present (daemon handled by procd)")
            else:
                notes.append("watchdog: /dev/watchdog0 not present")
        return notes

    def _apply_firewall(self, old: Dict[str, Any], new: Dict[str, Any]) -> List[str]:
        old_fw = old.get("firewall") or {}
        new_fw = new.get("firewall") or {}
        if old_fw == new_fw:
            return []
        notes = []
        try:
            # Wipe our previous vyos_ sections
            out = self._uci("show", "firewall").stdout
            for line in out.splitlines():
                if line.startswith("firewall.vyos_"):
                    sec = line.split(".")[1].split("=")[0]
                    try:
                        self._uci("delete", f"firewall.{sec}")
                    except subprocess.CalledProcessError:
                        pass
            # zones
            for name, cfg in (new_fw.get("zone") or {}).items():
                if not isinstance(cfg, dict):
                    continue
                s = f"vyos_zone_{name}"
                self._uci("set", f"firewall.{s}=zone")
                self._uci("set", f"firewall.{s}.name={name}")
                if cfg.get("network"):
                    self._uci("set", f"firewall.{s}.network={cfg['network']}")
                for d in ("input", "output", "forward"):
                    if cfg.get(d):
                        self._uci("set", f"firewall.{s}.{d}={cfg[d]}")
            # forwarding
            for name, cfg in (new_fw.get("forwarding") or {}).items():
                if not isinstance(cfg, dict):
                    continue
                s = f"vyos_fwd_{name}"
                self._uci("set", f"firewall.{s}=forwarding")
                if cfg.get("src"):
                    self._uci("set", f"firewall.{s}.src={cfg['src']}")
                if cfg.get("dest"):
                    self._uci("set", f"firewall.{s}.dest={cfg['dest']}")
            # rules
            for num, cfg in (new_fw.get("rule") or {}).items():
                if not isinstance(cfg, dict):
                    continue
                s = f"vyos_rule_{num}"
                self._uci("set", f"firewall.{s}=rule")
                self._uci("set", f"firewall.{s}.name={cfg.get('name', f'rule-{num}')}")
                self._uci("set", f"firewall.{s}.src={cfg.get('src', '*')}")
                if cfg.get("dest-port"):
                    self._uci("set", f"firewall.{s}.dest_port={cfg['dest-port']}")
                self._uci("set", f"firewall.{s}.target={cfg.get('target', 'ACCEPT')}")
            self._uci("commit", "firewall")
            subprocess.run(["/etc/init.d/firewall", "reload"],
                           capture_output=True, text=True, timeout=15)
            notes.append(f"firewall: {len(new_fw.get('zone') or {})} zones, "
                         f"{len(new_fw.get('rule') or {})} rules")
        except Exception as e:  # noqa: BLE001
            notes.append(f"firewall apply failed: {e}")
        return notes

    def _apply_firewall15(self, old, new):
        """VyOS-1.5-style firewall (ipv4/ipv6 direction rules) -> nftables."""
        old_fw = old.get("firewall") or {}
        new_fw = new.get("firewall") or {}
        keys = ("ipv4", "ipv6", "group", "global-options")
        if all(old_fw.get(k) == new_fw.get(k) for k in keys):
            return []
        path = os.path.join(self.base_dir, "firewall.nft")
        if not any(new_fw.get(k) for k in keys):
            try:
                subprocess.run(["nft", "delete", "table", "inet", "vyos_fw"],
                               capture_output=True, text=True, timeout=10)
            except (OSError, subprocess.SubprocessError):
                pass
            try:
                os.remove(path)
            except OSError:
                pass
            return ["firewall: VyOS-style rules removed"]
        text = render_firewall_nft(new_fw)
        os.makedirs(self.base_dir, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
        try:
            proc = subprocess.run(["nft", "-f", path], capture_output=True,
                                  text=True, timeout=15)
        except (OSError, subprocess.SubprocessError) as e:
            return [f"firewall: nft unavailable ({e}); rules kept in {path}"]
        if proc.returncode != 0:
            return [f"firewall apply failed: {(proc.stderr or '').strip()[:200]}"]
        count = text.count("meta nfproto")
        opts = new_fw.get("global-options") or {}
        sysctls = (
            ("all-ping", "net.ipv4.icmp_echo_ignore_all",
             lambda v: "0" if v else "1"),
            ("broadcast-ping", "net.ipv4.icmp_echo_ignore_broadcasts",
             lambda v: "0" if v else "1"),
            ("syn-cookies", "net.ipv4.tcp_syncookies",
             lambda v: "1" if v else "0"),
            ("log-martians", "net.ipv4.conf.all.log_martians",
             lambda v: "1" if v else "0"),
        )
        applied = 0
        for key, name, conv in sysctls:
            if key not in opts:
                continue
            try:
                subprocess.run(["sysctl", "-w", f"{name}={conv(bool(opts[key]))}"],
                               capture_output=True, text=True, timeout=5)
                applied += 1
            except (OSError, subprocess.SubprocessError):
                pass
        extra = f", {applied} sysctl(s)" if applied else ""
        return [f"firewall: applied {count} VyOS-style rule(s) via nft{extra}"]

    def _apply_nat66(self, old, new):
        old_n = old.get("nat66") or {}
        new_n = new.get("nat66") or {}
        if old_n == new_n:
            return []
        path = os.path.join(self.base_dir, "nat66.nft")

        def has_rules(holder):
            rules = (holder or {}).get("rule")
            return bool(rules) if isinstance(rules, dict) else bool(holder)

        if not (has_rules(new_n.get("source"))
                or has_rules(new_n.get("destination"))):
            try:
                subprocess.run(["nft", "delete", "table", "inet", "vyos_nat66"],
                               capture_output=True, text=True, timeout=10)
            except (OSError, subprocess.SubprocessError):
                pass
            try:
                os.remove(path)
            except OSError:
                pass
            return ["nat66: rules removed"]
        text = render_nat_nft(new_n, "ipv6")
        os.makedirs(self.base_dir, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
        try:
            proc = subprocess.run(["nft", "-f", path], capture_output=True,
                                  text=True, timeout=15)
        except (OSError, subprocess.SubprocessError) as e:
            return [f"nat66: nft unavailable ({e}); rules kept in {path}"]
        if proc.returncode != 0:
            return [f"nat66 apply failed: {(proc.stderr or '').strip()[:200]}"]
        return ["nat66: applied " + str(text.count("dnat to") + text.count("masquerade"))
                + " VyOS-style rule(s) via nft"]

    def _apply_nat(self, old, new):
        """VyOS-style NAT (source/destination) -> nft table inet vyos_nat."""
        old_n = old.get("nat") or {}
        new_n = new.get("nat") or {}
        if old_n == new_n:
            return []
        path = os.path.join(self.base_dir, "nat.nft")

        def has_rules(holder):
            rules = (holder or {}).get("rule")
            return bool(rules) if isinstance(rules, dict) else bool(holder)

        if not (has_rules(new_n.get("source"))
                or has_rules(new_n.get("destination"))):
            try:
                subprocess.run(["nft", "delete", "table", "inet", "vyos_nat"],
                               capture_output=True, text=True, timeout=10)
            except (OSError, subprocess.SubprocessError):
                pass
            try:
                os.remove(path)
            except OSError:
                pass
            return ["nat: rules removed"]
        text = render_nat_nft(new_n)
        os.makedirs(self.base_dir, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
        try:
            proc = subprocess.run(["nft", "-f", path], capture_output=True,
                                  text=True, timeout=15)
        except (OSError, subprocess.SubprocessError) as e:
            return [f"nat: nft unavailable ({e}); rules kept in {path}"]
        if proc.returncode != 0:
            return [f"nat apply failed: {(proc.stderr or '').strip()[:200]}"]
        return [f"nat: applied {text.count('masquerade') + text.count('dnat to')}"
                " VyOS-style rule(s) via nft"]

    def _sections_of_type(self, config: str, sec_type: str) -> List[str]:
        """Section names of a given UCI type, e.g. wireguard_wg0 peers."""
        try:
            out = self._uci("show", config).stdout
        except Exception:
            return []
        found = []
        for line in out.splitlines():
            lhs, _, value = line.partition("=")
            if "." in lhs[len(config) + 1:]:
                continue
            if value.strip("'\"") == sec_type:
                found.append(lhs.split(".", 1)[1])
        return found

    @staticmethod
    def _split_endpoint(endpoint: str) -> Tuple[str, Optional[str]]:
        """'1.2.3.4:51820' -> ('1.2.3.4', '51820'); '[::1]:51820' handled too."""
        host, port = endpoint, None
        if endpoint.startswith("[") and "]:" in endpoint:
            host, _, port = endpoint[1:].partition("]:")
        elif endpoint.count(":") == 1:
            host, _, port = endpoint.partition(":")
        if port is not None and not port.isdigit():
            host, port = endpoint, None
        return host, port

    def _apply_wireguard(self, old: Dict[str, Any], new: Dict[str, Any]) -> List[str]:
        old_wg = (old.get("interfaces") or {}).get("wireguard") or {}
        new_wg = (new.get("interfaces") or {}).get("wireguard") or {}
        if old_wg == new_wg:
            return []
        notes = []
        try:
            for gone in set(old_wg) - set(new_wg):
                try:
                    self._uci("delete", f"network.{gone}")
                except subprocess.CalledProcessError:
                    pass
                for section in self._sections_of_type("network", f"wireguard_{gone}"):
                    try:
                        self._uci("delete", f"network.{section}")
                    except subprocess.CalledProcessError:
                        pass
                subprocess.run(["ip", "link", "del", gone],
                               capture_output=True, timeout=5)
            for ifname, cfg in new_wg.items():
                if not isinstance(cfg, dict):
                    continue
                self._uci("set", f"network.{ifname}=interface")
                self._uci("set", f"network.{ifname}.proto=wireguard")
                if cfg.get("private-key"):
                    self._uci("set", f"network.{ifname}.private_key={cfg['private-key']}")
                if cfg.get("listen-port"):
                    self._uci("set", f"network.{ifname}.listen_port={cfg['listen-port']}")
                try:
                    self._uci("delete", f"network.{ifname}.addresses")
                except subprocess.CalledProcessError:
                    pass
                for a in _as_list(cfg.get("address")):
                    self._uci("add_list", f"network.{ifname}.addresses={a}")
                # Recreate peers from scratch so removed ones disappear.
                for section in self._sections_of_type("network", f"wireguard_{ifname}"):
                    try:
                        self._uci("delete", f"network.{section}")
                    except subprocess.CalledProcessError:
                        pass
                pfx = f"peer_{ifname}_"
                for pk, peer in (cfg.get("peer") or {}).items():
                    if not isinstance(peer, dict):
                        continue
                    slug = "".join(ch if ch.isalnum() else "_" for ch in pk[:20])
                    ps = f"{pfx}{slug}"
                    self._uci("set", f"network.{ps}=wireguard_{ifname}")
                    self._uci("set", f"network.{ps}.public_key={pk}")
                    if peer.get("endpoint"):
                        host, port = self._split_endpoint(str(peer["endpoint"]))
                        self._uci("set", f"network.{ps}.endpoint_host={host}")
                        if port:
                            self._uci("set", f"network.{ps}.endpoint_port={port}")
                    if peer.get("allowed-ips"):
                        self._uci("set", f"network.{ps}.allowed_ips={peer['allowed-ips']}")
            self._uci("commit", "network")
            subprocess.run(["/etc/init.d/network", "reload"],
                           capture_output=True, text=True, timeout=15)
            notes.append(f"wireguard: {list(new_wg.keys())}")
        except Exception as e:  # noqa: BLE001
            notes.append(f"wireguard apply failed: {e}")
        return notes

    def _apply_openvpn(self, old: Dict[str, Any], new: Dict[str, Any]) -> List[str]:
        old_ov = (old.get("interfaces") or {}).get("openvpn") or {}
        new_ov = (new.get("interfaces") or {}).get("openvpn") or {}
        if old_ov == new_ov:
            return []
        notes = []
        try:
            os.makedirs("/etc/openvpn", exist_ok=True)
            for vtun, cfg in new_ov.items():
                if not isinstance(cfg, dict):
                    continue
                conf_path = f"/etc/openvpn/{vtun}.conf"
                lines = ["# managed by vyoscli"]
                key_map = {
                    "mode": "mode",
                    "proto": "proto",
                    "port": "port",
                    "dev": "dev",
                    "ca": "ca",
                    "cert": "cert",
                    "key": "key",
                    "dh": "dh",
                    "server": "server",
                }
                for k, directive in key_map.items():
                    if cfg.get(k):
                        lines.append(f"{directive} {cfg[k]}")
                for p in _as_list(cfg.get("push")):
                    lines.append(f'push "{p}"')
                lines += ["persist-key", "persist-tun", "keepalive 10 120"]
                with open(conf_path, "w", encoding="utf-8") as f:
                    f.write("\n".join(lines) + "\n")
                # UCI pointer
                self._uci("set", f"openvpn.{vtun}=openvpn")
                self._uci("set", f"openvpn.{vtun}.enabled=1")
                self._uci("set", f"openvpn.{vtun}.config={conf_path}")
            self._uci("commit", "openvpn")
            subprocess.run(["/etc/init.d/openvpn", "restart"],
                           capture_output=True, text=True, timeout=20)
            notes.append(f"openvpn: {list(new_ov.keys())}")
        except Exception as e:  # noqa: BLE001
            notes.append(f"openvpn apply failed: {e}")
        return notes

    def _apply_tunnel(self, old: Dict[str, Any], new: Dict[str, Any]) -> List[str]:
        old_tn = (old.get("interfaces") or {}).get("tunnel") or {}
        new_tn = (new.get("interfaces") or {}).get("tunnel") or {}
        if old_tn == new_tn:
            return []
        notes = []
        try:
            for tun, cfg in new_tn.items():
                if not isinstance(cfg, dict):
                    continue
                enc = (cfg.get("encapsulation") or "gre").lower()
                if enc not in ("gre", "ipip"):
                    notes.append(f"  -> {tun}: unknown encapsulation {enc}, skip")
                    continue
                self._uci("set", f"network.{tun}=interface")
                self._uci("set", f"network.{tun}.proto={enc}")
                local = cfg.get("local-ip") or cfg.get("source-address")
                remote = cfg.get("remote-ip") or cfg.get("remote")
                if local:
                    self._uci("set", f"network.{tun}.localip={local}")
                if remote:
                    self._uci("set", f"network.{tun}.peeraddr={remote}")
                if cfg.get("address"):
                    self._uci("set", f"network.{tun}.ipaddr={cfg['address']}")
            self._uci("commit", "network")
            subprocess.run(["/etc/init.d/network", "reload"],
                           capture_output=True, text=True, timeout=15)
            notes.append(f"tunnels: {list(new_tn.keys())}")
        except Exception as e:  # noqa: BLE001
            notes.append(f"tunnel apply failed: {e}")
        return notes

    def _apply_vxlan(self, old: Dict[str, Any], new: Dict[str, Any]) -> List[str]:
        old_vx = (old.get("interfaces") or {}).get("vxlan") or {}
        new_vx = (new.get("interfaces") or {}).get("vxlan") or {}
        if old_vx == new_vx:
            return []
        notes = []
        try:
            for vx, cfg in new_vx.items():
                if not isinstance(cfg, dict):
                    continue
                # device section
                self._uci("set", f"network.{vx}=device")
                self._uci("set", f"network.{vx}.type=vxlan")
                self._uci("set", f"network.{vx}.name={vx}")
                if cfg.get("vni"):
                    self._uci("set", f"network.{vx}.vxlanid={cfg['vni']}")
                if cfg.get("local-ip"):
                    self._uci("set", f"network.{vx}.local={cfg['local-ip']}")
                if cfg.get("remote-ip"):
                    self._uci("set", f"network.{vx}.remote={cfg['remote-ip']}")
                # interface section for IP
                iface = f"{vx}_addr"
                self._uci("set", f"network.{iface}=interface")
                self._uci("set", f"network.{iface}.device={vx}")
                self._uci("set", f"network.{iface}.proto=static")
                if cfg.get("address"):
                    self._uci("set", f"network.{iface}.ipaddr={cfg['address']}")
            self._uci("commit", "network")
            subprocess.run(["/etc/init.d/network", "reload"],
                           capture_output=True, text=True, timeout=15)
            notes.append(f"vxlan: {list(new_vx.keys())}")
        except Exception as e:  # noqa: BLE001
            notes.append(f"vxlan apply failed: {e}")
        return notes

    @staticmethod
    def render_frr_conf(bgp: Dict[str, Any], route_maps: Dict[str, Any],
                        community_lists: Dict[str, Any],
                        hostname: str = "",
                        prefix_lists: Optional[Dict[str, Any]] = None,
                        as_path_lists: Optional[Dict[str, Any]] = None,
                        access_lists: Optional[Dict[str, Any]] = None,
                        ospf: Optional[Dict[str, Any]] = None,
                        rip: Optional[Dict[str, Any]] = None,
                        bfd: Optional[Dict[str, Any]] = None) -> List[str]:
        """Render /etc/frr/frr.conf for the OpenWrt frr package (no UCI)."""
        lines = [
            "# managed by vyoscli",
            "frr defaults traditional",
            f"hostname {hostname or 'OpenWrt'}",
            "log syslog informational",
            "service integrated-vtysh-config",
            "!",
        ]
        asn = bgp.get("local-as")
        if asn:
            lines.append(f"router bgp {asn}")
            if bgp.get("router-id"):
                lines.append(f" bgp router-id {bgp['router-id']}")
            # FRR 8+ enables RFC 8212 (eBGP requires policy) by default;
            # without route-maps every update is discarded as (Policy).
            lines.append(" no bgp ebgp-requires-policy")
            for name, pg in (bgp.get("peer-group") or {}).items():
                if not isinstance(pg, dict):
                    continue
                lines.append(f" neighbor {name} peer-group")
                if pg.get("remote-as"):
                    lines.append(f" neighbor {name} remote-as {pg['remote-as']}")
                if pg.get("update-source"):
                    lines.append(f" neighbor {name} update-source "
                                 f"{pg['update-source']}")
                if pg.get("route-map-import"):
                    lines.append(f" neighbor {name} route-map "
                                 f"{pg['route-map-import']} in")
            for ip, nb in (bgp.get("neighbor") or {}).items():
                if not isinstance(nb, dict):
                    continue
                if nb.get("peer-group"):
                    lines.append(f" neighbor {ip} peer-group {nb['peer-group']}")
                if nb.get("remote-as"):
                    lines.append(f" neighbor {ip} remote-as {nb['remote-as']}")
                if nb.get("description"):
                    lines.append(f" neighbor {ip} description {nb['description']}")
                if nb.get("route-map-in"):
                    lines.append(f" neighbor {ip} route-map {nb['route-map-in']} in")
                if nb.get("route-map-out"):
                    lines.append(f" neighbor {ip} route-map {nb['route-map-out']} out")
            networks = _as_list(bgp.get("network"))
            peers = list((bgp.get("neighbor") or {}).keys())
            groups = list((bgp.get("peer-group") or {}).keys())
            if networks or peers or groups:
                lines.append(" address-family ipv4 unicast")
                for net in networks:
                    lines.append(f"  network {net}")
                for ip in peers:
                    lines.append(f"  neighbor {ip} activate")
                    nb = (bgp.get("neighbor") or {}).get(ip) or {}
                    if (nb.get("soft-reconfiguration") or {}).get("inbound"):
                        lines.append(f"  neighbor {ip} "
                                     f"soft-reconfiguration inbound")
                for name in groups:
                    lines.append(f"  neighbor {name} activate")
                lines.append(" exit-address-family")
            lines.append("!")
        for num, body in (community_lists or {}).items():
            if not isinstance(body, dict):
                continue
            # command tree nests rules one level deeper: {rule: {10: {...}}}
            rules = body.get("rule") if isinstance(body.get("rule"), dict) else body
            for _ruleno, rule in rules.items():
                if not isinstance(rule, dict):
                    continue
                action = rule.get("action", "permit")
                regex = rule.get("regex") or ""
                if regex:
                    # regex membership needs FRR's "expanded" form
                    lines.append(f"bgp community-list expanded {num} "
                                 f"{action} {regex}")
                else:
                    lines.append(f"bgp community-list {num} {action}")
        ospf = ospf or {}
        if ospf:
            lines.append("router ospf")
            if ospf.get("router-id"):
                lines.append(f" ospf router-id {ospf['router-id']}")
            if ospf.get("log-adjacency-changes"):
                lines.append(" log-adjacency-changes")
            if ospf.get("default-information"):
                lines.append(" default-information originate")
            for area, cfg in (ospf.get("area") or {}).items():
                if not isinstance(cfg, dict) or not cfg.get("network"):
                    continue
                lines.append(f" network {cfg['network']} area {area}")
            for ifname, cfg in (ospf.get("interface") or {}).items():
                if not isinstance(cfg, dict) or not cfg.get("area"):
                    continue
                lines.append(f" interface {ifname} area {cfg['area']}")
                if cfg.get("cost"):
                    lines.append(f" ip ospf cost {cfg['cost']}")
                if cfg.get("priority"):
                    lines.append(f" ip ospf priority {cfg['priority']}")
                if cfg.get("passive"):
                    lines.append(f" passive-interface {ifname}")
            lines.append("!")
        rip = rip or {}
        if rip:
            lines.append("router rip")
            if rip.get("version"):
                lines.append(f" version {rip['version']}")
            if rip.get("network"):
                lines.append(f" network {rip['network']}")
            if rip.get("default-information"):
                lines.append(" default-information originate")
            lines.append("!")
        bfd = bfd or {}
        if bfd:
            lines.append("bfd")
            parts = []
            if bfd.get("interval"):
                parts.append(f"interval {bfd['interval']}")
            if bfd.get("min-rx"):
                parts.append(f"min-rx {bfd['min-rx']}")
            if bfd.get("multiplier"):
                parts.append(f"multiplier {bfd['multiplier']}")
            if parts:
                lines.append(" " + " ".join(parts))
            lines.append("!")
        for num, body in (access_lists or {}).items():
            if not isinstance(body, dict):
                continue
            rules = body.get("rule") if isinstance(body.get("rule"), dict) else body
            for _n, rule in rules.items():
                if not isinstance(rule, dict):
                    continue
                action = rule.get("action", "permit")
                src = (rule.get("source") or {}).get("address") or "any"
                dst = (rule.get("destination") or {}).get("address") or "any"
                proto = rule.get("protocol")
                sport = (rule.get("source") or {}).get("port")
                dport = (rule.get("destination") or {}).get("port")
                if proto and proto != "ip":
                    body_txt = f"access-list {num} {action} {proto} {src}"
                    if sport:
                        body_txt += f" eq {sport}"
                    body_txt += f" {dst}"
                    if dport:
                        body_txt += f" eq {dport}"
                else:
                    body_txt = f"access-list {num} {action} {src}"
                lines.append(body_txt)
        for name, body in (prefix_lists or {}).items():
            if not isinstance(body, dict):
                continue
            rules = body.get("rule") if isinstance(body.get("rule"), dict) else body
            for seq, rule in rules.items():
                if not isinstance(rule, dict) or not rule.get("prefix"):
                    continue
                action = rule.get("action", "permit")
                entry = f"ip prefix-list {name} seq {seq} {action} {rule['prefix']}"
                if rule.get("ge"):
                    entry += f" ge {rule['ge']}"
                if rule.get("le"):
                    entry += f" le {rule['le']}"
                lines.append(entry)
        for name, body in (as_path_lists or {}).items():
            if not isinstance(body, dict):
                continue
            rules = body.get("rule") if isinstance(body.get("rule"), dict) else body
            for _n, rule in rules.items():
                if not isinstance(rule, dict) or not rule.get("regex"):
                    continue
                lines.append(f"ip as-path access-list {name} "
                             f"{rule.get('action', 'permit')} {rule['regex']}")
        lines.append("!")
        for name, body in (route_maps or {}).items():
            if not isinstance(body, dict):
                continue
            for action, rules in body.items():
                if action not in ("permit", "deny"):
                    continue
                for ruleno, rbody in (rules or {}).items():
                    if not isinstance(rbody, dict):
                        continue
                    lines.append(f"route-map {name} {action} {ruleno}")
                    for key, value in (rbody.get("match") or {}).items():
                        if key == "prefix-list":
                            lines.append(f" match ip address prefix-list {value}")
                        elif key == "as-path":
                            lines.append(f" match as-path {value}")
                        elif isinstance(value, dict):
                            for inner in value.values():
                                lines.append(f" match {key} {inner}")
                        else:
                            lines.append(f" match {key} {value}")
                    for key, value in (rbody.get("set") or {}).items():
                        lines.append(f" set {key} {value}")
        lines.append("!")
        return lines

    @staticmethod
    def _set_frr_daemons(enable_bgpd: bool, enable_ospfd: bool = False,
                         enable_ripd: bool = False,
                         enable_bfd: bool = False) -> None:
        path = "/etc/frr/daemons"
        try:
            with open(path, encoding="utf-8") as f:
                text = f.read()
        except OSError:
            return

        def put(body: str, key: str, value: str) -> str:
            pattern = re.compile(rf"^{re.escape(key)}=.*$", re.M)
            line = f"{key}={value}"
            return (pattern.sub(line, body) if pattern.search(body) else
                    body.rstrip("\n") + "\n" + line + "\n")

        text = put(text, "zebra", "yes")
        text = put(text, "bgpd", "yes" if enable_bgpd else "no")
        text = put(text, "ospfd", "yes" if enable_ospfd else "no")
        text = put(text, "ripd", "yes" if enable_ripd else "no")
        text = put(text, "bfdd", "yes" if enable_bfd else "no")
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)

    def _apply_bgp(self, old, new):
        new_b = (new.get("protocols") or {}).get("bgp") or {}
        old_b = (old.get("protocols") or {}).get("bgp") or {}
        rmaps = (new.get("policy") or {}).get("route-map") or {}
        old_rmaps = (old.get("policy") or {}).get("route-map") or {}
        new_protos = new.get("protocols") or {}
        old_protos = old.get("protocols") or {}
        ospf = new_protos.get("ospf") or {}
        rip = new_protos.get("rip") or {}
        bfd = new_protos.get("bfd") or {}
        pol = new.get("policy") or {}
        old_pol = old.get("policy") or {}
        comlists = pol.get("community-list") or {}
        old_comlists = old_pol.get("community-list") or {}
        prefix_lists = pol.get("prefix-list") or {}
        old_prefix = old_pol.get("prefix-list") or {}
        as_path_lists = pol.get("as-path-list") or {}
        old_as_path = old_pol.get("as-path-list") or {}
        access_lists = pol.get("access-list") or {}
        old_access = old_pol.get("access-list") or {}
        if (old_b == new_b and old_rmaps == rmaps
                and old_comlists == comlists and old_prefix == prefix_lists
                and old_as_path == as_path_lists and old_access == access_lists
                and old_protos.get("ospf") == ospf
                and old_protos.get("rip") == rip
                and old_protos.get("bfd") == bfd):
            return []
        notes: List[str] = []
        if not os.path.isdir("/etc/frr") or shutil.which("vtysh") is None:
            return ["bgp: frr is not installed, config kept in vyoscli JSON"]
        try:
            hostname = (new.get("system") or {}).get("host-name") or ""
            text = "\n".join(self.render_frr_conf(
                new_b, rmaps, comlists, hostname,
                prefix_lists=prefix_lists, as_path_lists=as_path_lists,
                access_lists=access_lists, ospf=ospf, rip=rip,
                bfd=bfd)) + "\n"
            with open("/etc/frr/frr.conf", "w", encoding="utf-8") as f:
                f.write(text)
            os.chmod("/etc/frr/frr.conf", 0o640)
            self._set_frr_daemons(bool(new_b.get("local-as")),
                                  bool(ospf), bool(rip), bool(bfd))
            subprocess.run(["/etc/init.d/frr", "start"],
                           capture_output=True, text=True, timeout=25)
            subprocess.run(["vtysh", "-b"], capture_output=True,
                           text=True, timeout=30)
            if new_b.get("local-as"):
                notes.append(f"bgp: AS{new_b['local-as']}, "
                             f"{len(new_b.get('neighbor') or {})} peers")
            else:
                notes.append("bgp: disabled (bgpd=no)")
        except Exception as e:  # noqa: BLE001
            notes.append(f"bgp apply failed: {e}")
        return notes

    def _apply_interface_roles(self, old: Dict[str, Any], new: Dict[str, Any]) -> List[str]:
        old_if = old.get("interfaces") or {}
        new_if = new.get("interfaces") or {}
        notes = []
        try:
            # ---- wan/lan role ----
            # Legacy JSON keeps interfaces.role = {lan: eth1}; the command tree
            # writes interfaces.lan.device = eth1. Accept both.
            old_role = dict(old_if.get("role") or {})
            new_role = dict(new_if.get("role") or {})
            for role in ("lan", "wan"):
                cfg = new_if.get(role)
                if isinstance(cfg, dict) and cfg.get("device"):
                    new_role[role] = cfg["device"]
                old_cfg = old_if.get(role)
                if isinstance(old_cfg, dict) and old_cfg.get("device"):
                    old_role[role] = old_cfg["device"]
            if old_role != new_role:
                for role, dev in new_role.items():
                    self._uci("set", f"network.{role}=interface")
                    self._uci("set", f"network.{role}.device={dev}")
                    if role == "wan":
                        self._uci("set", f"network.{role}.proto=dhcp")
                    else:
                        self._uci("set", f"network.{role}.proto=static")
                notes.append(f"interface roles: {new_role}")
            # ---- dummy ----
            old_dm = old_if.get("dummy") or {}
            new_dm = new_if.get("dummy") or {}
            if old_dm != new_dm:
                # Removed dummies must lose their UCI sections, otherwise the
                # interface comes back on the next boot.
                for gone in set(old_dm) - set(new_dm):
                    for section in (gone, f"{gone}_dev"):
                        try:
                            self._uci("delete", f"network.{section}")
                        except subprocess.CalledProcessError:
                            pass
                for dm, cfg in new_dm.items():
                    if not isinstance(cfg, dict):
                        continue
                    # netifd needs a dummy *device*; an interface alone points
                    # at a device that never exists.
                    self._uci("set", f"network.{dm}_dev=device")
                    self._uci("set", f"network.{dm}_dev.type=dummy")
                    self._uci("set", f"network.{dm}_dev.name={dm}")
                    self._uci("set", f"network.{dm}=interface")
                    self._uci("set", f"network.{dm}.device={dm}")
                    self._uci("set", f"network.{dm}.proto=static")
                    addrs = _as_list(cfg.get("address"))
                    if addrs:
                        try:
                            self._uci("delete", f"network.{dm}.ipaddr")
                        except subprocess.CalledProcessError:
                            pass
                        for addr in addrs:
                            self._uci("add_list", f"network.{dm}.ipaddr={addr}")
                notes.append(f"dummy ifaces: {list(new_dm.keys())}")
            self._uci("commit", "network")
            subprocess.run(["/etc/init.d/network", "reload"],
                           capture_output=True, text=True, timeout=15)
        except Exception as e:  # noqa: BLE001
            notes.append(f"interface roles apply failed: {e}")
        return notes

    def _apply_wireless(self, old: Dict[str, Any], new: Dict[str, Any]) -> List[str]:
        old_wl = (old.get("interfaces") or {}).get("wireless") or {}
        new_wl = (new.get("interfaces") or {}).get("wireless") or {}
        if old_wl == new_wl:
            return []
        notes: List[str] = []
        if not os.path.exists("/etc/config/wireless"):
            # No radio => no wireless config on this box; do not create one.
            return ["wireless: /etc/config/wireless missing (no radio?), skipped"]
        try:
            for gone in set(old_wl) - set(new_wl):
                try:
                    self._uci("delete", f"wireless.vyos_{gone}")
                except subprocess.CalledProcessError:
                    pass
            SEC_MAP = {"wpa2": "psk2", "wpa3": "sae", "none": "none", "open": "none"}
            for ifname, cfg in new_wl.items():
                if not isinstance(cfg, dict):
                    continue
                # wlanN -> radioN
                num = "".join(ch for ch in ifname if ch.isdigit()) or "0"
                radio = f"radio{num}"
                dev = f"vyos_{radio}"
                ifc = f"vyos_{ifname}"
                # wifi-device
                self._uci("set", f"wireless.{dev}=wifi-device")
                self._uci("set", f"wireless.{dev}.type=mac80211")
                if cfg.get("channel"):
                    self._uci("set", f"wireless.{dev}.channel={cfg['channel']}")
                hw = cfg.get("hw-mode", "11g")
                self._uci("set", f"wireless.{dev}.hwmode={hw}")
                self._uci("set", f"wireless.{dev}.htmode=HT20")
                # wifi-iface
                self._uci("set", f"wireless.{ifc}=wifi-iface")
                self._uci("set", f"wireless.{ifc}.device={dev}")
                self._uci("set", f"wireless.{ifc}.network={cfg.get('network', 'lan')}")
                self._uci("set", f"wireless.{ifc}.mode={cfg.get('mode', 'ap')}")
                if cfg.get("ssid"):
                    self._uci("set", f"wireless.{ifc}.ssid={cfg['ssid']}")
                sec = SEC_MAP.get(cfg.get("security", "wpa2"), "psk2")
                self._uci("set", f"wireless.{ifc}.encryption={sec}")
                if cfg.get("passphrase"):
                    self._uci("set", f"wireless.{ifc}.key={cfg['passphrase']}")
            self._uci("commit", "wireless")
            subprocess.run(["wifi", "reload"], capture_output=True, text=True, timeout=15)
            notes.append(f"wireless: {len(new_wl)} SSID(s) configured")
        except Exception as e:  # noqa: BLE001
            notes.append(f"wireless apply failed: {e}")
        return notes

    def _apply_smartdns(self, old: Dict[str, Any], new: Dict[str, Any]) -> List[str]:
        old_sd = (old.get("service") or {}).get("smartdns") or {}
        new_sd = (new.get("service") or {}).get("smartdns") or {}
        if old_sd == new_sd:
            return []
        notes = []
        try:
            # Remove all sections we previously created.
            try:
                out = self._uci("show", "smartdns").stdout
            except Exception:
                out = ""
            for line in out.splitlines():
                if line.startswith("smartdns.vyos_"):
                    section = line.split(".")[1].split("=")[0]
                    try:
                        self._uci("delete", f"smartdns.{section}")
                    except subprocess.CalledProcessError:
                        pass
            # Main smartdns section: reuse the stock anonymous one if present.
            enabled = 1 if new_sd.get("enabled") else 0
            try:
                self._uci("get", "smartdns.@smartdns[0]")
                main = "smartdns.@smartdns[0]"
            except subprocess.CalledProcessError:
                self._uci("set", "smartdns.vyos_main=smartdns")
                main = "smartdns.vyos_main"
            self._uci("set", f"{main}.enabled={enabled}")
            self._uci("set", f"{main}.port={new_sd.get('port', 5333)}")
            scm = new_sd.get("speed-check-mode", "")
            if scm:
                self._uci("set", f"{main}.speed_check_mode={scm}")
            # Upstream servers: smartdns UCI has a "server" section type;
            # server_group is what domain-rules refer to.
            for name, cfg in (new_sd.get("server") or {}).items():
                if not isinstance(cfg, dict):
                    continue
                s = f"vyos_srv_{self._slug(name)}"
                self._uci("set", f"smartdns.{s}=server")
                self._uci("set", f"smartdns.{s}.server_group={name}")
                if cfg.get("ip"):
                    self._uci("set", f"smartdns.{s}.ip={cfg['ip']}")
                if cfg.get("port"):
                    self._uci("set", f"smartdns.{s}.port={cfg['port']}")
                if cfg.get("type"):
                    self._uci("set", f"smartdns.{s}.type={cfg['type']}")
            # domain-rule: attach the referenced domain-set's domains to the
            # first upstream in "forward". File-backed sets cannot be expressed
            # in UCI and are reported instead of silently dropped.
            domain_sets = new_sd.get("domain-set") or {}
            for name, cfg in (new_sd.get("domain-rule") or {}).items():
                if not isinstance(cfg, dict):
                    continue
                dset = domain_sets.get(cfg.get("domain-set")) or {}
                domains = _as_list(dset.get("domain"))
                forwards = _as_list(cfg.get("forward"))
                if not domains:
                    if dset.get("file"):
                        notes.append(f"smartdns rule {name}: domain-set file "
                                     f"{dset['file']} kept as-is (not mapped to UCI)")
                    continue
                s = f"vyos_drule_{self._slug(name)}"
                self._uci("set", f"smartdns.{s}=domain-rule")
                for domain in domains:
                    self._uci("add_list", f"smartdns.{s}.domain={domain}")
                if forwards:
                    self._uci("set", f"smartdns.{s}.server_group={forwards[0]}")
            if new_sd.get("address"):
                notes.append("smartdns: 'address' entries are not mapped to "
                             "UCI yet (use domain-rule/address.conf)")
            # forbid-aaaa has no main-section UCI option on OpenWrt's smartdns.
            if new_sd.get("forbid-aaaa"):
                notes.append("smartdns: forbid-aaaa is not applied via UCI")
            self._uci("commit", "smartdns")
            subprocess.run(["/etc/init.d/smartdns", "restart"],
                           capture_output=True, text=True, timeout=15)
            notes.append(f"smartdns {'enabled' if enabled else 'disabled'} on port {new_sd.get('port', 5333)}")
        except Exception as e:  # noqa: BLE001
            notes.append(f"smartdns apply failed: {e} (is the smartdns package installed?)")
        return notes

    @staticmethod
    def merge_crontab(existing: str, jobs: Dict[str, Any]) -> List[str]:
        """Rebuild /etc/crontabs/root: user lines + our managed blocks.

        Managed blocks are delimited by marker comments, so the whole block
        (markers *and* the cron line) must be dropped before re-adding jobs —
        otherwise deleting a job leaves the crontab entry behind.
        """
        lines: List[str] = []
        inside_block = False
        for line in existing.splitlines():
            if line.startswith("# --- vyoscli:begin:"):
                inside_block = True
                continue
            if line.startswith("# --- vyoscli:end:"):
                inside_block = False
                continue
            if inside_block:
                continue
            lines.append(line)
        while lines and not lines[-1].strip():
            lines.pop()
        for name, cfg in jobs.items():
            if not isinstance(cfg, dict):
                continue
            schedule = cfg.get("schedule")
            script = cfg.get("script")
            if not schedule or not script:
                continue
            lines.append(f"# --- vyoscli:begin:{name} ---")
            if cfg.get("description"):
                lines.append(f"# {cfg['description']}")
            lines.append(f"{schedule} {script}")
            lines.append(f"# --- vyoscli:end:{name} ---")
        return lines

    def _apply_crontab(self, old: Dict[str, Any], new: Dict[str, Any]) -> List[str]:
        old_cron = (old.get("service") or {}).get("crontab") or {}
        new_cron = (new.get("service") or {}).get("crontab") or {}
        if old_cron == new_cron:
            return []
        notes = []
        tab_path = "/etc/crontabs/root"
        try:
            existing = ""
            if os.path.exists(tab_path):
                with open(tab_path, encoding="utf-8") as f:
                    existing = f.read()
            lines = self.merge_crontab(existing, new_cron)
            with open(tab_path, "w", encoding="utf-8") as f:
                f.write("\n".join(lines) + "\n")
            os.chmod(tab_path, 0o600)
            subprocess.run(["/etc/init.d/cron", "restart"],
                           capture_output=True, text=True, timeout=10)
            notes.append(f"crontab: {len(new_cron)} managed job(s) written")
        except Exception as e:  # noqa: BLE001
            notes.append(f"crontab apply failed: {e}")
        return notes

    @staticmethod
    def _slug(text: str) -> str:
        return "".join(ch if ch.isalnum() else "_" for ch in str(text)).strip("_")

    def _iface_for_subnet(self, new: Dict[str, Any], cidr: str) -> Optional[str]:
        """Find the interface whose address falls inside ``cidr``."""
        try:
            net = ipaddress.IPv4Network(cidr, strict=False)
        except ValueError:
            return None
        ifaces = new.get("interfaces") or {}
        for group in ("ethernet", "bridge", "loopback", "dummy", "wireguard"):
            for name, cfg in (ifaces.get(group) or {}).items():
                if not isinstance(cfg, dict):
                    continue
                addrs = cfg.get("address") or []
                if isinstance(addrs, str):
                    addrs = [addrs]
                for addr in addrs:
                    try:
                        if ipaddress.IPv4Interface(addr).ip in net:
                            return name
                    except ValueError:
                        continue
        return None

    def _apply_dhcp(self, old: Dict[str, Any], new: Dict[str, Any]) -> List[str]:
        old_d = ((old.get("service") or {}).get("dhcp-server") or {})
        new_d = ((new.get("service") or {}).get("dhcp-server") or {})
        if old_d == new_d:
            return []
        notes: List[str] = []
        try:
            # Replace our own sections so deleted subnets/leases disappear.
            out = self._uci("show", "dhcp").stdout
            for line in out.splitlines():
                if line.startswith("dhcp.vyos_dhcp_"):
                    sec = line.split(".")[1].split("=")[0]
                    try:
                        self._uci("delete", f"dhcp.{sec}")
                    except subprocess.CalledProcessError:
                        pass

            shared = new_d.get("shared-network-name") or {}
            for sname, body in shared.items():
                if not isinstance(body, dict):
                    continue
                for cidr, cfg in (body.get("subnet") or {}).items():
                    if not isinstance(cfg, dict):
                        continue
                    try:
                        net = ipaddress.IPv4Network(cidr, strict=False)
                    except ValueError:
                        notes.append(f"dhcp {sname}: invalid subnet {cidr}, skipped")
                        continue
                    iface = (cfg.get("interface") or body.get("interface")
                             or self._iface_for_subnet(new, cidr))
                    if not iface:
                        notes.append(f"dhcp {sname}/{cidr}: no interface holds an "
                                     f"address in this subnet; set "
                                     f"shared-network-name {sname} interface <uci-net>")
                        continue
                    sec = f"vyos_dhcp_{self._slug(sname)}_{self._slug(cidr)}"
                    self._uci("set", f"dhcp.{sec}=dhcp")
                    self._uci("set", f"dhcp.{sec}.interface={iface}")
                    self._uci("set", f"dhcp.{sec}.dhcpv4=server")

                    # range 0 { start, stop } -> start offset / limit
                    ranges = cfg.get("range") or {}
                    rng = ranges.get("0") if isinstance(ranges, dict) else None
                    if isinstance(rng, dict) and rng.get("start") and rng.get("stop"):
                        try:
                            start = ipaddress.IPv4Address(rng["start"])
                            stop = ipaddress.IPv4Address(rng["stop"])
                            if start not in net or stop not in net:
                                notes.append(f"dhcp {sname}/{cidr}: range "
                                             f"{start}-{stop} outside subnet, skipped")
                            else:
                                offset = int(start) - int(net.network_address)
                                self._uci("set", f"dhcp.{sec}.start={offset}")
                                self._uci("set",
                                          f"dhcp.{sec}.limit={int(stop) - int(start) + 1}")
                        except ValueError:
                            notes.append(f"dhcp {sname}/{cidr}: bad range, skipped")

                    if cfg.get("lease"):
                        self._uci("set", f"dhcp.{sec}.leasetime={cfg['lease']}")

                    try:
                        self._uci("delete", f"dhcp.{sec}.dhcp_option")
                    except subprocess.CalledProcessError:
                        pass
                    if cfg.get("default-router"):
                        self._uci("add_list",
                                  f"dhcp.{sec}.dhcp_option=router,{cfg['default-router']}")
                    dns = cfg.get("name-server") or []
                    if isinstance(dns, str):
                        dns = [dns]
                    for server in dns:
                        self._uci("add_list",
                                  f"dhcp.{sec}.dhcp_option=option:dns,{server}")
                    if cfg.get("domain-name"):
                        self._uci("add_list",
                                  f"dhcp.{sec}.dhcp_option=domain,{cfg['domain-name']}")
                    if cfg.get("domain-search"):
                        self._uci("add_list",
                                  f"dhcp.{sec}.dhcp_option=option:domain-search,"
                                  f"{cfg['domain-search']}")

                    for mname, mapping in (cfg.get("static-mapping") or {}).items():
                        if not isinstance(mapping, dict):
                            continue
                        host = f"vyos_dhcp_host_{self._slug(sname)}_{self._slug(mname)}"
                        self._uci("set", f"dhcp.{host}=host")
                        self._uci("set", f"dhcp.{host}.name={mname}")
                        if mapping.get("mac-address"):
                            self._uci("set", f"dhcp.{host}.mac={mapping['mac-address']}")
                        if mapping.get("ip-address"):
                            self._uci("set", f"dhcp.{host}.ip={mapping['ip-address']}")
                    notes.append(f"dhcp {sname}/{cidr} -> {iface}")
            self._uci("commit", "dhcp")
            subprocess.run(["/etc/init.d/dnsmasq", "reload"],
                           capture_output=True, text=True, timeout=10)
        except Exception as e:  # noqa: BLE001
            notes.append(f"dhcp apply failed: {e}")
        return notes

    def _apply_ssh_acl(self, old, new):
        def acl_of(cfg):
            ssh = (cfg.get("service") or {}).get("ssh") or {}
            return (ssh.get("access-control") or {}, ssh.get("acl") or {})

        old_ac, old_acl = acl_of(old)
        new_ac, new_acl = acl_of(new)
        if (old_ac, old_acl) == (new_ac, new_acl):
            return []
        path = os.path.join(self.base_dir, "ssh-acl.nft")
        permits = _as_list(new_acl.get("permit"))
        allows = _as_list((new_ac.get("allow") or {}).get("address"))
        denies = _as_list((new_ac.get("deny") or {}).get("address"))
        if not (permits or allows or denies):
            try:
                subprocess.run(["nft", "delete", "table", "inet", "vyos_ssh"],
                               capture_output=True, text=True, timeout=10)
            except (OSError, subprocess.SubprocessError):
                pass
            try:
                os.remove(path)
            except OSError:
                pass
            return ["ssh-acl: removed"]
        ssh = (new.get("service") or {}).get("ssh") or {}
        port = ssh.get("port") or 22
        lines = ["table inet vyos_ssh {"]
        if permits:
            lines.append("  set permit { type ipv4_addr; flags interval; "
                         "elements = { " + ", ".join(permits) + " } }")
        lines.append("  chain input { type filter hook input priority -20; "
                     "policy accept;")
        if permits:
            lines.append(f"    tcp dport {port} ip saddr @permit accept")
            lines.append(f"    tcp dport {port} drop")
        else:
            for addr in allows:
                lines.append(f"    tcp dport {port} ip saddr {addr} accept")
            for addr in denies:
                lines.append(f"    tcp dport {port} ip saddr {addr} drop")
        lines += ["  }", "}"]
        text = "\n".join(lines) + "\n"
        os.makedirs(self.base_dir, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
        try:
            proc = subprocess.run(["nft", "-f", path], capture_output=True,
                                  text=True, timeout=15)
        except (OSError, subprocess.SubprocessError) as e:
            return [f"ssh-acl: nft unavailable ({e})"]
        if proc.returncode != 0:
            return [f"ssh-acl apply failed: {(proc.stderr or '').strip()[:160]}"]
        if permits:
            return [f"ssh-acl: allow-list {len(permits)} prefix(es)"]
        return [f"ssh-acl: {len(allows) + len(denies)} rule(s)"]

    def _apply_ssh(self, old: Dict[str, Any], new: Dict[str, Any]) -> List[str]:
        old_s = (old.get("service") or {}).get("ssh") or {}
        new_s = (new.get("service") or {}).get("ssh") or {}
        if old_s == new_s:
            return []
        notes = []
        try:
            idx = "@dropbear[0]"
            if new_s.get("port"):
                self._uci("set", f"dropbear.{idx}.Port={new_s['port']}")
            if new_s.get("listen-address"):
                self._uci("set", f"dropbear.{idx}.ListenAddress={new_s['listen-address']}")
            self._uci("set", f"dropbear.{idx}.PasswordAuth={'on' if new_s.get('password-auth', True) else 'off'}")
            self._uci("set", f"dropbear.{idx}.RootPasswordAuth={'on' if new_s.get('root-login', True) else 'off'}")
            self._uci("commit", "dropbear")
            subprocess.run(["/etc/init.d/dropbear", "restart"],
                           capture_output=True, text=True, timeout=10)
            notes.append(f"ssh: port={new_s.get('port',22)} password_auth={new_s.get('password-auth',True)}")
        except Exception as e:  # noqa: BLE001
            notes.append(f"ssh apply failed: {e}")
        return notes

    def _apply_adguard(self, old: Dict[str, Any], new: Dict[str, Any]) -> List[str]:
        old_ag = (old.get("service") or {}).get("adguard") or {}
        new_ag = (new.get("service") or {}).get("adguard") or {}
        if old_ag == new_ag:
            return []
        notes = []
        try:
            # OpenWrt's adguardhome UCI section is "config" and only carries
            # enabled/workdir; DNS and web ports live in /etc/adguardhome.yaml.
            self._uci("set", "adguardhome.config=adguardhome")
            self._uci("set",
                      f"adguardhome.config.enabled={'1' if new_ag.get('enabled') else '0'}")
            self._uci("commit", "adguardhome")
            subprocess.run(["/etc/init.d/adguardhome", "restart"],
                           capture_output=True, text=True, timeout=15)
            if new_ag.get("enabled"):
                notes.append("adguardhome: enabled (DNS/web ports come from "
                             "/etc/adguardhome.yaml; UCI only toggles the service)")
            else:
                notes.append("adguardhome: disabled")
        except Exception as e:  # noqa: BLE001
            notes.append(f"adguard apply failed: {e}")
        return notes
    def _apply_dnsmasq(self, old, new):
        old_dm = (old.get("service") or {}).get("dnsmasq") or {}
        new_dm = (new.get("service") or {}).get("dnsmasq") or {}
        if old_dm == new_dm:
            return []
        notes = []
        try:
            self._uci("set", "dhcp.@dnsmasq[0].port=" + str(new_dm.get("port", 53)))
            self._uci("set", "dhcp.@dnsmasq[0].listenaddress=" + new_dm.get("listen-address", "0.0.0.0"))
            self._uci("commit", "dhcp")
            subprocess.run(["/etc/init.d/dnsmasq", "restart"],
                           capture_output=True, text=True, timeout=10)
            notes.append(f"dnsmasq: {new_dm.get('listen-address','0.0.0.0')}:{new_dm.get('port',53)}")
        except Exception as e:
            notes.append(f"dnsmasq apply failed: {e}")
        return notes

    def _apply_traffic_policy(self, old, new):
        old_tp = (old.get("traffic-policy") or {}).get("shaper") or {}
        new_tp = (new.get("traffic-policy") or {}).get("shaper") or {}
        if old_tp == new_tp:
            return []
        notes = []
        try:
            for name, cfg in new_tp.items():
                if not isinstance(cfg, dict):
                    continue
                iface = cfg.get("interface", "eth0")
                bandwidth = cfg.get("bandwidth", "100mbit")
                per_ip = cfg.get("per-ip", "10mbit")
                # root qdisc + default class (replace => idempotent re-commit)
                subprocess.run(["tc", "qdisc", "replace", "dev", iface, "root",
                                "handle", "1:", "htb", "default", "10"],
                               capture_output=True, timeout=5)
                subprocess.run(["tc", "class", "replace", "dev", iface, "parent", "1:",
                                "classid", "1:10", "htb", "rate", bandwidth,
                                "ceil", bandwidth],
                               capture_output=True, timeout=5)
                notes.append(f"qos {name}: {iface} total={bandwidth} "
                             f"(per-ip {per_ip} not enforced yet)")
        except Exception as e:
            notes.append(f"qos failed: {e}")
        return notes

    def _apply_sqm(self, old, new):
        old_sqm = (old.get("service") or {}).get("sqm") or {}
        new_sqm = (new.get("service") or {}).get("sqm") or {}
        if old_sqm == new_sqm:
            return []
        notes = []
        try:
            iface = new_sqm.get("interface", "eth1")
            download = new_sqm.get("download", 100000)
            upload = new_sqm.get("upload", 10000)
            qdisc = new_sqm.get("qdisc", "cake")
            # OpenWrt's sqm config uses one named queue section per interface.
            sec = f"sqm.{iface}"
            self._uci("set", f"{sec}=queue")
            self._uci("set", f"{sec}.enabled=1")
            self._uci("set", f"{sec}.interface={iface}")
            self._uci("set", f"{sec}.download={download}")
            self._uci("set", f"{sec}.upload={upload}")
            self._uci("set", f"{sec}.qdisc={qdisc}")
            self._uci("set", f"{sec}.script="
                      + ("piece_of_cake.qos" if qdisc == "cake" else "simple.qos"))
            self._uci("commit", "sqm")
            subprocess.run(["/etc/init.d/sqm", "restart"],
                           capture_output=True, text=True, timeout=10)
            notes.append(f"sqm: {iface} down={download}kbps up={upload}kbps qdisc={qdisc}")
        except Exception as e:
            notes.append(f"sqm failed: {e}")
        return notes

    def _apply_kcp(self, old, new):
        old_acc = (old.get("service") or {}).get("kcp") or {}
        new_acc = (new.get("service") or {}).get("kcp") or {}
        if old_acc == new_acc:
            return []
        notes = []
        try:
            for name, cfg in new_acc.items():
                if not isinstance(cfg, dict):
                    continue
                mode = cfg.get("mode", "c")
                kcp_mode = cfg.get("kcp-mode", "fast3")
                local_ip = cfg.get("local-ip", "0.0.0.0")
                local_port = cfg.get("local-port", 9991)
                remote_ip = cfg.get("remote-ip", "")
                remote_port = cfg.get("remote-port", 0)
                if mode == "s":
                    # server: -t remote:port -l local:port
                    cmd = f"kcptun-server -t {remote_ip}:{remote_port} -l {local_ip}:{local_port} -mode {kcp_mode} -nocomp -sockbuf 16777217 -dscp 46"
                else:
                    # client: -r remote:port -l local:port
                    cmd = f"kcptun-client -r {remote_ip}:{remote_port} -l {local_ip}:{local_port} -mode {kcp_mode} -nocomp -autoexpire 900 -sockbuf 16777217 -dscp 46"
                conf = "#!/bin/sh /etc/rc.common\n"
                conf += "START=99\n"
                conf += "start() {\n"
                conf += f"    {cmd} > /tmp/acc-{name}.log 2>&1 &\n"
                conf += "}\n"
                conf += "stop() {\n"
                conf += f"    pkill -f 'kcptun-{mode}' 2>/dev/null\n"
                conf += "}\n"
                script = f"/etc/init.d/kcp_{name}"
                with open(script, "w", encoding="utf-8") as f:
                    f.write(conf)
                os.chmod(script, 0o755)
                subprocess.run([script, "restart"],
                               capture_output=True, text=True, timeout=10)
            notes.append(f"kcp: {len(new_acc)} tunnels")
        except Exception as e:
            notes.append(f"kcp apply failed: {e}")
        return notes

    def _apply_tcp_accelerate(self, old, new):
        old_tcp = (old.get("service") or {}).get("tcp-accelerate") or {}
        new_tcp = (new.get("service") or {}).get("tcp-accelerate") or {}
        if old_tcp == new_tcp:
            return []
        notes = []
        try:
            cc = new_tcp.get("congestion-control", "bbr")
            # sysctl
            subprocess.run(["sysctl", "-w", f"net.ipv4.tcp_congestion_control={cc}"],
                           capture_output=True, text=True, timeout=5)
            if new_tcp.get("fq-codel", True):
                subprocess.run(["sysctl", "-w", "net.core.default_qdisc=fq_codel"],
                               capture_output=True, text=True, timeout=5)
            notes.append(f"tcp cc = {cc}, qdisc = fq_codel")
        except Exception as e:
            notes.append(f"tcp accelerate failed: {e}")
        return notes

    def _apply_policy(self, old, new):
        old_pol = (old.get("policy") or {}).get("route-redirect") or {}
        new_pol = (new.get("policy") or {}).get("route-redirect") or {}
        if old_pol == new_pol:
            return []
        notes = []
        try:
            # flush old table
            subprocess.run(["nft", "add", "table", "inet", "vyoscli_policy"],
                           capture_output=True, timeout=5)
            subprocess.run(["nft", "flush", "table", "inet", "vyoscli_policy"],
                           capture_output=True, timeout=5)
            for name, pol in new_pol.items():
                if not isinstance(pol, dict):
                    continue
                chain = f"rredir_{name}"
                subprocess.run(["nft", "add", "chain", "inet", "vyoscli_policy", chain,
                                "{ type nat hook prerouting priority -100; }"],
                               capture_output=True, timeout=5)
                for rnum, rule in (pol.get("rule") or {}).items():
                    dport = rule.get("dport")
                    rto = rule.get("redirect-to")
                    if dport and rto:
                        subprocess.run(["nft", "add", "rule", "inet", "vyoscli_policy", chain,
                                        f"tcp dport {dport} redirect to {rto}"],
                                       capture_output=True, timeout=5)
            notes.append(f"policy: {len(new_pol)} route-redirect")
        except Exception as e:
            notes.append(f"policy apply failed: {e}")
        return notes

    def _apply_vrf(self, old, new):
        old_vrf = (old.get("vrf") or {}).get("name") or {}
        new_vrf = (new.get("vrf") or {}).get("name") or {}
        if old_vrf == new_vrf:
            return []
        notes = []
        try:
            for name in set(old_vrf.keys()) - set(new_vrf.keys()):
                subprocess.run(["ip", "link", "del", name],
                               capture_output=True, timeout=5)
            for name, cfg in new_vrf.items():
                table = cfg.get("table", 1000)
                r = subprocess.run(["ip", "link", "show", name],
                                   capture_output=True, timeout=5)
                if r.returncode != 0:
                    subprocess.run(["ip", "link", "add", name, "type", "vrf", "table", str(table)],
                                   capture_output=True, timeout=5)
                    subprocess.run(["ip", "link", "set", name, "up"],
                                   capture_output=True, timeout=5)
            notes.append(f"vrf: {len(new_vrf)} instances")
        except Exception as e:
            notes.append(f"vrf apply failed: {e}")
        return notes

    @staticmethod
    def _have_tool(name: str) -> bool:
        return shutil.which(name) is not None

    def _user_exists(self, name: str) -> bool:
        try:
            return subprocess.run(["id", "-u", name], capture_output=True,
                                  timeout=5).returncode == 0
        except OSError:
            return False

    def _create_user(self, name: str, notes: List[str]) -> bool:
        """OpenWrt has no shadow suite: busybox adduser, else useradd."""
        for cmd in (["adduser", "-D", "-s", "/bin/ash", "-h", f"/home/{name}", name],
                    ["useradd", "-m", "-s", "/bin/ash", name]):
            if not self._have_tool(cmd[0]):
                continue
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            if r.returncode == 0:
                return True
            notes.append(f"user {name}: {cmd[0]} failed: {r.stderr.strip()[:120]}")
        notes.append(f"user {name}: neither adduser nor useradd available")
        return False

    def _set_password(self, name: str, password: str, notes: List[str]) -> None:
        if self._have_tool("chpasswd"):
            subprocess.run(["chpasswd"], input=f"{name}:{password}\n", text=True,
                           capture_output=True, timeout=10)
            return
        if self._have_tool("passwd"):
            r = subprocess.run(["passwd", name], input=f"{password}\n{password}\n",
                               text=True, capture_output=True, timeout=10)
            if r.returncode != 0:
                msg = (r.stderr or r.stdout).strip()[:120]
                notes.append(f"user {name}: passwd failed: {msg}")
            return
        notes.append(f"user {name}: no chpasswd/passwd available, password not set")

    def _set_disabled(self, name: str, disabled: bool, notes: List[str]) -> None:
        flag = "-L" if disabled else "-U"
        if self._have_tool("usermod"):
            subprocess.run(["usermod", flag, name], capture_output=True,
                           text=True, timeout=5)
        elif self._have_tool("passwd"):
            flag = "-l" if disabled else "-u"
            r = subprocess.run(["passwd", flag, name], capture_output=True,
                               text=True, timeout=5)
            if r.returncode != 0:
                notes.append(f"user {name}: could not {'lock' if disabled else 'unlock'}")
        else:
            notes.append(f"user {name}: cannot lock/unlock (no usermod/passwd)")

    def _apply_login(self, old, new):
        old_login = (old.get("system") or {}).get("login") or {}
        new_login = (new.get("system") or {}).get("login") or {}
        if old_login == new_login:
            return []
        notes: List[str] = []
        try:
            for name, user in (new_login.get("user") or {}).items():
                if not isinstance(user, dict):
                    continue
                auth = user.get("authentication") or {}
                if not self._user_exists(name):
                    if not self._create_user(name, notes):
                        continue
                    notes.append(f"user {name}: created")
                password = auth.get("plaintext-password") or user.get("password")
                if password:
                    self._set_password(name, password, notes)
                if user.get("disable") is not None:
                    self._set_disabled(name, bool(user.get("disable")), notes)
                keys = auth.get("public-keys") or user.get("public-keys") or {}
                if keys:
                    ssh_dir = f"/home/{name}/.ssh"
                    os.makedirs(ssh_dir, exist_ok=True)
                    lines = []
                    for kid, key in keys.items():
                        if isinstance(key, dict) and key.get("key"):
                            lines.append(f"{key.get('type', 'ssh-rsa')} "
                                         f"{key['key']} {kid}")
                    path = os.path.join(ssh_dir, "authorized_keys")
                    with open(path, "w", encoding="utf-8") as f:
                        f.write("\n".join(lines) + "\n")
                    os.chmod(path, 0o600)
                    subprocess.run(["chown", "-R", name, ssh_dir],
                                   capture_output=True, timeout=5)
            notes.append(f"login: {len(new_login.get('user') or {})} user(s)")
        except Exception as e:  # noqa: BLE001
            notes.append(f"login apply failed: {e}")
        return notes

    # IKE DH group number -> strongSwan proposal keyword.
    DH_GROUP_KEYWORD = {
        2: "modp1024", 5: "modp1536", 14: "modp2048", 15: "modp3072",
        16: "modp4096", 17: "modp6144", 18: "modp8192",
        19: "ecp256", 20: "ecp384", 21: "ecp521",
    }

    def _ipsec_proposal(self, group: Dict[str, Any], with_dh: bool) -> str:
        props = []
        for _num, p in (group.get("proposal") or {}).items():
            if not isinstance(p, dict):
                continue
            parts = [p.get("encryption", "aes256"), p.get("hash", "sha256")]
            if with_dh:
                dh = int(p.get("dh-group", 14) or 14)
                parts.append(self.DH_GROUP_KEYWORD.get(dh, f"modp{dh * 256}"))
            props.append("-".join(parts))
        return ";".join(props)

    def _apply_ipsec(self, old, new):
        old_ip = (old.get("vpn") or {}).get("ipsec") or {}
        new_ip = (new.get("vpn") or {}).get("ipsec") or {}
        if old_ip == new_ip:
            return []
        peers = ((new_ip.get("site-to-site") or {}).get("peer")
                 or new_ip.get("peer") or {})
        remote = new_ip.get("remote-access") or {}

        ike_groups = new_ip.get("ike-group") or {}
        esp_groups = new_ip.get("esp-group") or {}
        notes: List[str] = []
        try:
            conf = [
                "# managed by vyoscli",
                "config setup",
                '  charondebug="ike 1, cfg 1"',
                "conn %default",
                "  keyexchange=ikev2",
                "  authby=secret",
                "  dpddelay=30s",
                "  dpdtimeout=120s",
                "  dpdaction=clear",
                "  auto=add",
            ]

            def ike_of(name: str) -> str:
                if name and name in ike_groups:
                    return self._ipsec_proposal(ike_groups[name], True)
                return "aes256-sha256-modp2048" if name else ""

            def esp_of(name: str) -> str:
                if name and name in esp_groups:
                    return self._ipsec_proposal(esp_groups[name], False)
                return "aes256-sha256" if name else ""

            for peer_ip, peer in peers.items():
                if not isinstance(peer, dict):
                    continue
                conf.append(f"conn peer-{peer_ip}")
                conf.append(f"  left={peer.get('local-address', '0.0.0.0')}")
                if peer.get("local-id"):
                    conf.append(f"  leftid={peer['local-id']}")
                conf.append(f"  right={peer.get('remote-address', peer_ip)}")
                if peer.get("remote-id"):
                    conf.append(f"  rightid={peer['remote-id']}")
                ike = ike_of(peer.get("ike-group", ""))
                esp = esp_of(peer.get("esp-group", ""))
                if ike:
                    conf.append(f"  ike={ike}")
                if esp:
                    conf.append(f"  esp={esp}")
                for _num, tun in (peer.get("tunnel") or {}).items():
                    if not isinstance(tun, dict):
                        continue
                    conf.append(f"  leftsubnet={tun.get('local-prefix', '0.0.0.0/0')}")
                    conf.append(f"  rightsubnet={tun.get('remote-prefix', '0.0.0.0/0')}")
                conf.append("  auto=start")

            if remote.get("enabled"):
                conf.append("conn remote-access")
                conf.append(f"  left={remote.get('local-address') or '%any'}")
                if remote.get("local-id"):
                    conf.append(f"  leftid={remote['local-id']}")
                conf.append("  leftauth=psk")
                conf.append("  right=%any")
                conf.append("  rightauth=psk")
                conf.append(f"  rightsourceip={remote.get('pool-start', '10.100.0.10')}"
                            f"-{remote.get('pool-end', '10.100.0.100')}")
                dns = _as_list(remote.get("dns"))
                if dns:
                    conf.append(f"  rightdns={','.join(map(str, dns))}")

            with open("/etc/ipsec.conf", "w", encoding="utf-8") as f:
                f.write("\n".join(conf) + "\n")
            os.chmod("/etc/ipsec.conf", 0o600)

            secrets = []
            if remote.get("enabled") and remote.get("secret"):
                secrets.append(f"{remote.get('local-id') or '%any'} %any : "
                               f"PSK \"{remote['secret']}\"")
            for peer_ip, peer in peers.items():
                if isinstance(peer, dict) and peer.get("secret"):
                    secrets.append(f"{peer.get('local-address', '%any')} "
                                   f"{peer.get('remote-address', peer_ip)} : "
                                   f"PSK \"{peer['secret']}\"")
            with open("/etc/ipsec.secrets", "w", encoding="utf-8") as f:
                f.write("\n".join(secrets) + "\n")
            os.chmod("/etc/ipsec.secrets", 0o600)

            subprocess.run(["/etc/init.d/ipsec", "restart"],
                           capture_output=True, text=True, timeout=30)
            notes.append(f"ipsec: {len(peers)} peer(s)"
                         + (", remote-access" if remote.get("enabled") else ""))
        except Exception as e:  # noqa: BLE001
            notes.append(f"ipsec apply failed: {e}")
        return notes

    def _apply_console_server(self, old, new):
        old_cs = (old.get("service") or {}).get("console-server") or {}
        new_cs = (new.get("service") or {}).get("console-server") or {}
        if old_cs == new_cs:
            return []
        notes = []
        try:
            # write conserver.cf
            cf = ["### Autogenerated by vyoscli ###",
                  "config * {",
                  "    primaryport 3109;",
                  "    daemonmode false;",
                  "}",
                  "default * {",
                  '    motd "OpenWrt Console Server";',
                  "    logfile /var/log/conserver/&.log;",
                  '    timestamp "";',
                  "    rw *;",
                  "}"]
            for dev, cfg in new_cs.items():
                if not isinstance(cfg, dict):
                    continue
                speed = cfg.get("speed", 9600)
                parity = cfg.get("parity", "none")
                stop = cfg.get("stop-bits", "1")
                cf.append(f"console {dev} {{")
                cf.append("    master localhost;")
                cf.append("    type device;")
                cf.append(f"    device /dev/{dev};")
                cf.append(f"    baud {speed};")
                cf.append(f"    parity {parity};")
                if stop == "1":
                    cf.append("    options !cstopb;")
                else:
                    cf.append("    options cstopb;")
                cf.append("}")
            cf.append("access * {")
            cf.append("    trusted localhost;")
            cf.append("    allowed localhost;")
            cf.append("}")
            with open("/etc/conserver/conserver.cf", "w", encoding="utf-8") as f:
                f.write("\n".join(cf) + "\n")
            subprocess.run(["/etc/init.d/conserver", "restart"],
                           capture_output=True, text=True, timeout=10)
            # stop per-device dropbear instances from a previous commit
            for pidfile in glob.glob("/var/run/vyoscli-console-*.pid"):
                try:
                    with open(pidfile, encoding="utf-8") as f:
                        pid = int(f.read().strip())
                    os.kill(pid, 15)
                except (OSError, ValueError):
                    pass
                try:
                    os.remove(pidfile)
                except OSError:
                    pass
            dropbear = shutil.which("dropbear") or "/usr/sbin/dropbear"
            console_cmd = shutil.which("console") or "console"
            key = "/etc/dropbear/dropbear_rsa_host_key"
            for dev, cfg in new_cs.items():
                port = cfg.get("ssh-port")
                if not port:
                    continue
                if not os.path.exists(dropbear):
                    notes.append(f"console {dev}: dropbear not installed")
                    continue
                pidfile = f"/var/run/vyoscli-console-{dev}.pid"
                argv = [dropbear, "-j", "-k",
                        "-c", f"{console_cmd} {dev}",
                        "-P", pidfile, "-p", str(port)]
                if os.path.exists(key):
                    argv[1:1] = ["-r", key]
                subprocess.Popen(argv, stdin=subprocess.DEVNULL,
                                 stdout=subprocess.DEVNULL,
                                 stderr=subprocess.DEVNULL)
                notes.append(f"console {dev}: port {port} baud {cfg.get('speed', 9600)}")
        except Exception as e:
            notes.append(f"console-server apply failed: {e}")
        return notes

    def _apply_service_disable(self, old, new):
        # scan each service sub-node for a "disable" leaf
        # map vyoscli service name -> init.d script
        svc_map = {
            "ssh": "dropbear",
            "smartdns": "smartdns",
            "adguard": "adguardhome",
            "dnsmasq": "dnsmasq",
            "dhcp-server": "dnsmasq",
            "crontab": "cron",
        }
        old_svc = old.get("service") or {}
        new_svc = new.get("service") or {}
        notes = []
        for vyos_name, init_name in svc_map.items():
            old_dis = bool((old_svc.get(vyos_name) or {}).get("disable"))
            new_dis = bool((new_svc.get(vyos_name) or {}).get("disable"))
            if old_dis == new_dis:
                continue
            try:
                if new_dis:
                    subprocess.run(["/etc/init.d/" + init_name, "stop"],
                                   capture_output=True, text=True, timeout=10)
                    subprocess.run(["/etc/init.d/" + init_name, "disable"],
                                   capture_output=True, text=True, timeout=5)
                    notes.append(f"{vyos_name}: stopped and disabled")
                else:
                    subprocess.run(["/etc/init.d/" + init_name, "enable"],
                                   capture_output=True, text=True, timeout=5)
                    subprocess.run(["/etc/init.d/" + init_name, "start"],
                                   capture_output=True, text=True, timeout=10)
                    notes.append(f"{vyos_name}: enabled and started")
            except Exception as e:
                notes.append(f"{vyos_name}: control failed: {e}")
        return notes

    def _apply_containers(self, old: Dict[str, Any], new: Dict[str, Any]) -> List[str]:
        old_c = (old.get("container") or {})
        new_c = (new.get("container") or {})
        if old_c == new_c:
            return []
        notes = []
        if shutil.which("podman") is None:
            return ["(podman install failed; container config kept in vyoscli JSON)"]
        try:
            # Remove containers that disappeared from candidate.
            for name in old_c:
                if name not in new_c:
                    subprocess.run(["podman", "rm", "-f", name],
                                   capture_output=True, text=True, timeout=30)
                    notes.append(f"removed container {name}")
            # Recreate containers whose spec changed.
            for name, cfg in new_c.items():
                if not isinstance(cfg, dict):
                    continue
                if old_c.get(name) == cfg:
                    continue  # unchanged, leave running
                # Force recreate on any change.
                subprocess.run(["podman", "rm", "-f", name],
                               capture_output=True, text=True, timeout=30)
                cmd = ["podman", "run", "-d", "--name", name,
                       f"--restart={cfg.get('restart', 'always')}"]
                if cfg.get("network"):
                    cmd += ["--network", cfg["network"]]
                for p in _as_list(cfg.get("port")):
                    cmd += ["-p", p]
                for v in _as_list(cfg.get("volume")):
                    cmd += ["-v", v]
                for k, v in (cfg.get("environment") or {}).items():
                    cmd += ["-e", f"{k}={v}"]
                if cfg.get("command"):
                    cmd += [cfg["image"], cfg["command"]]
                else:
                    cmd += [cfg["image"]]
                r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
                if r.returncode == 0:
                    notes.append(f"started container {name} ({cfg.get('image')})")
                else:
                    notes.append(f"container {name} failed: {r.stderr.strip()[:200]}")
        except Exception as e:  # noqa: BLE001
            notes.append(f"container apply failed: {e}")
        return notes
    # ---------- history ----------
    def _snapshot_current_running(self) -> str:
        now = datetime.now()
        ts = now.strftime("%Y-%m-%d_%H-%M-%S") + f"_{now.microsecond // 1000:03d}"
        path = os.path.join(self.history_dir, f"{ts}.json")
        self._dump(path, self.running)
        # prune
        snaps = sorted(os.listdir(self.history_dir))
        while len(snaps) > HISTORY_KEEP:
            os.remove(os.path.join(self.history_dir, snaps.pop(0)))
        return path

    def list_history(self) -> List[Tuple[str, str]]:
        if not os.path.isdir(self.history_dir):
            return []
        out = []
        for fn in sorted(os.listdir(self.history_dir), reverse=True):
            if fn.endswith(".json"):
                out.append((fn[:-5], os.path.join(self.history_dir, fn)))
        return out

    # ---------- rollback timer ----------
    def arm_rollback_timer(self, seconds: int, snapshot_path: str) -> int:
        """Fork a detached timer process; returns its pid."""
        import sys
        log = open("/tmp/vyoscli-rollback.log", "ab")
        proc = subprocess.Popen(
            [sys.executable, "-m", "vyoscli",
             "--rollback-wait", str(seconds), snapshot_path],
            stdout=log, stderr=log, stdin=subprocess.DEVNULL,
            start_new_session=True,
        )
        self._dump(self.rollback_conf, {"pid": proc.pid,
                                        "deadline": time.time() + seconds,
                                        "snapshot": snapshot_path})
        return proc.pid

    def disarm_rollback_timer(self) -> Optional[int]:
        conf = self.pending_rollback()
        if conf is None:
            return None
        pid = conf.get("pid")
        if pid:
            try:
                os.kill(pid, 15)
            except OSError:
                pass
        self._remove_quietly(self.rollback_conf)
        return pid

    def pending_rollback(self) -> Optional[Dict[str, Any]]:
        if not os.path.exists(self.rollback_conf):
            return None
        try:
            with open(self.rollback_conf, encoding="utf-8") as f:
                conf = json.load(f)
        except (OSError, ValueError):
            return None
        # A timer left over from a reboot can never fire: drop it instead of
        # letting "commit confirm" claim a rollback is still pending.
        if float(conf.get("deadline", 0)) < time.time():
            self._remove_quietly(self.rollback_conf)
            return None
        return conf

    @staticmethod
    def _remove_quietly(path: str) -> None:
        try:
            os.remove(path)
        except OSError:
            pass

    # ---------- commit / confirm / rollback ----------
    def commit(self, confirmed_minutes: int = 0) -> str:
        if not self.modified():
            return "No changes to commit."
        # Validate before touching anything: a rejected commit must leave the
        # running config and the candidate exactly as they were.
        conflicts = self._check_dns_conflicts(self.candidate)
        if conflicts:
            return "Commit aborted: " + "; ".join(conflicts)

        snapshot = self._snapshot_current_running()
        old_running = copy.deepcopy(self.running)
        self.running = copy.deepcopy(self.candidate)
        self._touched = {}
        notes = self._apply_all(old_running, self.running)
        # Persist only after the backend has been driven, so a crashed apply
        # cannot leave running.json claiming a state the device is not in.
        self._dump(self.running_path, self.running)
        self._record_applied()

        out = "Commit complete."
        if confirmed_minutes > 0:
            pid = self.arm_rollback_timer(confirmed_minutes * 60, snapshot)
            out += (f" Auto-rollback armed for {confirmed_minutes} min "
                    f"(pid {pid}). Run 'commit confirm' to keep these changes.")
        for n in notes:
            out += f"\n  - {n}"
        return out

    def sync(self, only_drift: bool = True) -> str:
        """Re-apply running.json to the backend, ignoring the JSON diff.

        Drift repair path: ``show system drift`` lists what was changed behind
        vyoscli's back, ``sync`` writes the desired state again. With
        ``only_drift`` (default) just the owning apply steps of the drifted
        sections are replayed, so a hand-edited hostname does not reload
        network/firewall or restart containers.
        """
        if not self._have_uci():
            return "sync: no uci on this host"
        drifted = self.drift()
        owners: Optional[set] = None
        if only_drift and drifted is not None:
            if not drifted:
                return "Sync: no drift, nothing to do."
            manifest = self._load_applied()
            owners = set()
            for section, _state in drifted:
                entry = manifest.get(section)
                owner = entry.get("owner") if isinstance(entry, dict) else None
                if not owner:
                    owners = None        # unknown provenance -> full sync
                    break
                owners.add(owner)
        self._touched = {}
        # A full sync must not recreate every container (rm -f + run).
        skip = {"containers"} if owners is None else None
        notes = self._apply_all({}, copy.deepcopy(self.running), only=owners,
                                skip=skip)
        if skip:
            notes.append("containers untouched during full sync")
        self._record_applied()
        failed = any("failed" in note for note in notes)
        if owners is not None and not failed:
            # A "missing" section that the owning step did not recreate is no
            # longer part of the desired config (e.g. the interface was removed
            # from JSON by hand): stop reporting it as drift.
            manifest = self._load_applied()
            pruned = []
            for section, state in drifted:
                if state == "missing" and self._section_digest(section) == "absent":
                    manifest.pop(section, None)
                    pruned.append(section)
            if pruned:
                self._dump(self.applied_path, manifest)
        scope = "drift sections" if owners is not None else "full"
        out = f"Sync complete ({scope})."
        for n in notes:
            out += f"\n  - {n}"
        return out

    def confirm(self) -> str:
        if self.pending_rollback() is None:
            return "No pending confirmed commit."
        pid = self.disarm_rollback_timer()
        if pid is None:
            return "No pending confirmed commit."
        return f"Confirmed. Rollback timer (pid {pid}) cancelled."

    def rollback_to(self, snapshot_ts: Optional[str] = None) -> str:
        """Roll back to a snapshot. If snapshot_ts is None, use the most recent."""
        history = self.list_history()
        if not history:
            return "No snapshots to roll back to."
        if snapshot_ts is None:
            ts, path = history[0]
        else:
            match = [h for h in history if h[0] == snapshot_ts]
            if not match:
                return f"no such snapshot: {snapshot_ts}"
            ts, path = match[0]
        old_running = copy.deepcopy(self.running)
        with open(path, encoding="utf-8") as f:
            self.running = json.load(f)
        self.candidate = copy.deepcopy(self.running)
        self._dump(self.running_path, self.running)
        self._dump(self.candidate_path, self.candidate)
        self._touched = {}
        notes = self._apply_all(old_running, self.running)
        self._record_applied()
        self.disarm_rollback_timer()
        out = f"Rolled back to {ts}."
        for n in notes:
            out += f"\n  - {n}"
        return out

    def discard(self) -> str:
        self.candidate = copy.deepcopy(self.running)
        self._dump(self.candidate_path, self.candidate)
        return "Changes discarded."

    def compare(self) -> str:
        running_cmds = set(self.render_set_commands(self.running))
        candidate_cmds = set(self.render_set_commands(self.candidate))
        added = sorted(candidate_cmds - running_cmds)
        removed = sorted(running_cmds - candidate_cmds)
        if not added and not removed:
            return "No changes."
        out = []
        if added:
            out.append("[added]")
            out.extend(f"  + {c}" for c in added)
        if removed:
            out.append("[removed]")
            out.extend(f"  - {c}" for c in removed)
        return "\n".join(out)

    def save(self) -> str:
        self._dump(self.running_path, self.running)
        return f"Saved to {self.running_path}"

    # ---------- rendering ----------
    @staticmethod
    def _is_unset(v: Any) -> bool:
        """True for values that must not be rendered.

        Unset defaults (None / "" / empty containers) would otherwise render
        as ``set x None``; replaying that export stores the literal string
        "None" and silently corrupts the config.
        """
        return v is None or v == "" or (isinstance(v, (dict, list)) and not v)

    @staticmethod
    def _quote_token(tok: Any) -> str:
        if isinstance(tok, bool):
            return "true" if tok else "false"
        return shlex.quote(str(tok))

    def render_set_commands(self, cfg: Optional[Dict[str, Any]] = None, prefix: List[str] = None) -> List[str]:
        cfg = cfg if cfg is not None else self.candidate
        prefix = prefix or []
        out: List[str] = []
        if isinstance(cfg, dict):
            for k in sorted(cfg.keys()):
                v = cfg[k]
                if self._is_unset(v):
                    continue
                if isinstance(v, dict):
                    out.extend(self.render_set_commands(v, prefix + [k]))
                elif isinstance(v, list):
                    for item in v:
                        if self._is_unset(item):
                            continue
                        out.append("set " + " ".join(
                            self._quote_token(t) for t in prefix + [k, item]))
                else:
                    out.append("set " + " ".join(
                        self._quote_token(t) for t in prefix + [k, v]))
        return out

    def render_tree(self, cfg: Optional[Dict[str, Any]] = None, indent: int = 0) -> str:
        """VyOS-style indented '{' tree, e.g.::
              system {
                  host-name Test
              }
        """
        cfg = cfg if cfg is not None else self.candidate
        pad = "    " * indent
        lines: List[str] = []
        for k in sorted(cfg.keys()):
            v = cfg[k]
            if self._is_unset(v):
                continue
            if isinstance(v, dict):
                body = self.render_tree(v, indent + 1)
                if not body:
                    continue        # whole subtree is unset -> omit it
                lines.append(f"{pad}{k} {{")
                lines.append(body)
                lines.append(f"{pad}}}")
            elif isinstance(v, list):
                for item in v:
                    if self._is_unset(item):
                        continue
                    lines.append(f"{pad}{k} {item}")
            else:
                lines.append(f"{pad}{k} {v}")
        return "\n".join(lines)
