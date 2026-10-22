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

import json
import os
import copy
import shutil
import subprocess
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
        "bridge": {},     # br0 -> [ports]
        "dummy": {},      # dum0 -> {address}
        "wireguard": {},  # wg0 -> {address, private-key, listen-port, peer: {}}
        "openvpn": {},    # vtun0 -> {mode, proto, port, dev, ca, cert, key, dh, server, push}
        "tunnel": {},     # tun0 -> {encapsulation, local-ip, remote-ip, address}
        "vxlan": {},      # vxlan0 -> {vni, local-ip, remote-ip, address}
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
    },
    "vrf": {
        "name": {},   # name -> {table: int}
    },
    "traffic-policy": {
        "shaper": {},  # name -> {interface, bandwidth, per-ip}
    },
    "interfaces": {
        "bridge": {},  # br0 -> {port: [], mac, mac-rebinding, address, vlan-aware, vlan: {vid: {untagged: [], tagged: []}}}
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
        "route-map": {},   # name -> {permit: {rule: {set: {}, match: {}}}},
        "community-list": {},  # num -> {rule: {regex, description, action}},
    },
    "service": {
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
            "fq_codel": True,
        },
        "fec": {},   # UDPspeeder config
        "kcp": {},   # name -> {mode, local-listen-ip, local-listen-port, remote-listen-ip, remote-listen-port, destination-ip, destination-port, kcp-mode, key}

        "crontab": {},          # name -> {schedule, script, description}
        "dhcp": {},             # name -> {subnet, gateway, dns, domain, domain-search, range-start, range-end, static: {name: {ip, mac}}}
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


class ConfigStore:
    def __init__(self, base_dir: str = "/etc/vyoscli") -> None:
        self.base_dir = base_dir
        self.running_path = os.path.join(base_dir, "running.json")
        self.candidate_path = os.path.join(base_dir, "candidate.json")
        self.history_dir = os.path.join(base_dir, "history")
        self.rollback_conf = os.path.join(base_dir, "rollback.conf")
        self.running: Dict[str, Any] = {}
        self.candidate: Dict[str, Any] = {}
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
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, sort_keys=True)

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

    def set_value(self, path: List[str], value: str) -> None:
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
        else:
            node[leaf] = value

    def delete_path(self, path: List[str]) -> None:
        if not path:
            return
        *parents, leaf = path
        node = self._nav(self.candidate, parents, create=False)
        if isinstance(node, dict) and leaf in node:
            del node[leaf]
        elif isinstance(node, list) and leaf in node:
            node.remove(leaf)

    # ---------- transactions ----------
    def modified(self) -> bool:
        return self.candidate != self.running

    # ---------- UCI helpers ----------
    @staticmethod
    def _have_uci() -> bool:
        return shutil.which("uci") is not None

    @staticmethod
    def _uci(*args: str) -> subprocess.CompletedProcess:
        return subprocess.run(["uci", *args], check=True,
                              capture_output=True, text=True)

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
    def _ensure_package(self, pkg: str, notes: List[str]) -> bool:
        """Install pkg on demand via opkg. Idempotent. Notes progress."""
        if shutil.which("opkg") is None:
            return False
        chk = subprocess.run(["opkg", "list-installed", pkg],
                             capture_output=True, text=True, timeout=10)
        if chk.returncode == 0 and pkg in chk.stdout:
            return True
        notes.append(f"installing optional package: {pkg} ...")
        r = subprocess.run(["opkg", "install", pkg],
                           capture_output=True, text=True, timeout=600)
        if r.returncode == 0:
            notes.append(f"  -> {pkg} installed")
            return True
        notes.append(f"  -> {pkg} install FAILED: {r.stderr.strip()[:200]}")
        return False

    def _ensure_ss(self) -> None:
        """Auto-install ip-full if ss is missing."""
        try:
            subprocess.run(["ss", "--version"], capture_output=True, timeout=5)
        except FileNotFoundError:
            try:
                subprocess.run(["opkg", "install", "ip-full"],
                               capture_output=True, text=True, timeout=60)
            except Exception:
                pass

    def _address_port_in_use(self, ip: str, port: int) -> bool:
        """Return True if binding (ip, port) conflicts with an existing listener."""
        self._ensure_ss()
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

    def _apply_all(self, old: Dict[str, Any], new: Dict[str, Any]) -> List[str]:
        """按依赖优先级下发配置：system -> interfaces -> protocols -> vpn -> service"""
        notes: List[str] = []
        if not self._have_uci():
            notes.append("(no uci on this host, changes kept in vyoscli JSON only)")
            return notes

        # 1. system 基础（hostname/DNS/login）
        notes.extend(self._apply_hostname(old, new))
        notes.extend(self._apply_system_meta(old, new))
        notes.extend(self._apply_name_servers(old, new))
        notes.extend(self._apply_system_dns(old, new))
        notes.extend(self._apply_login(old, new))

        # 2. interfaces（IP/bridge/wireless/vrf）
        notes.extend(self._apply_interfaces(old, new))
        notes.extend(self._apply_wireless(old, new))
        notes.extend(self._apply_interface_roles(old, new))
        notes.extend(self._apply_vrf(old, new))

        # 3. protocols（static route/BGP/policy）
        notes.extend(self._apply_static_routes(old, new))
        notes.extend(self._apply_bgp(old, new))
        notes.extend(self._apply_policy(old, new))

        # 4. firewall / nat
        notes.extend(self._apply_firewall(old, new))
        notes.extend(self._apply_nat(old, new))

        # 5. vpn（wireguard/openvpn/tunnel/vxlan/ipsec）
        notes.extend(self._apply_wireguard(old, new))
        notes.extend(self._apply_openvpn(old, new))
        notes.extend(self._apply_tunnel(old, new))
        notes.extend(self._apply_vxlan(old, new))
        notes.extend(self._apply_ipsec(old, new))

        # 6. service（dhcp/ssh/dns/sqm/kcp/qos）
        notes.extend(self._apply_dhcp(old, new))
        notes.extend(self._apply_ssh(old, new))
        notes.extend(self._apply_adguard(old, new))
        notes.extend(self._apply_dnsmasq(old, new))
        notes.extend(self._apply_smartdns(old, new))
        notes.extend(self._apply_traffic_policy(old, new))
        notes.extend(self._apply_sqm(old, new))
        notes.extend(self._apply_kcp(old, new))
        notes.extend(self._apply_tcp_accelerate(old, new))
        notes.extend(self._apply_console_server(old, new))
        notes.extend(self._apply_containers(old, new))

        # 7. other
        notes.extend(self._apply_crontab(old, new))
        notes.extend(self._apply_service_disable(old, new))
        return notes

    def _apply_interfaces(self, old: Dict[str, Any], new: Dict[str, Any]) -> List[str]:
        old_if = old.get("interfaces") or {}
        new_if = new.get("interfaces") or {}
        if old_if == new_if:
            return []
        notes: List[str] = []
        eth = (new_if.get("ethernet") or {})
        for ifname, cfg in eth.items():
            if not isinstance(cfg, dict) or ifname == "lo":
                continue
            section = self._find_uci_section("network", "ifname", ifname)
            if section is None:
                section = f"vyos_{ifname}"
                self._uci("set", f"network.{section}=interface")
                notes.append(f"uci: created network.{section} for {ifname}")
            self._uci("set", f"network.{section}.ifname={ifname}")
            self._uci("set", f"network.{section}.proto=static")
            try:
                self._uci("delete", f"network.{section}.ipaddr")
            except subprocess.CalledProcessError:
                pass
            addrs = cfg.get("address") or []
            if isinstance(addrs, str):
                addrs = [addrs]
            for addr in addrs:
                self._uci("add_list", f"network.{section}.ipaddr={addr}")
        # bridge VLAN
        bridges = (new_if.get("bridge") or {})
        for brname, brcfg in bridges.items():
            if not isinstance(brcfg, dict):
                continue
            br_sec = f"vyos_br_{brname}"
            self._uci("set", f"network.{br_sec}=interface")
            self._uci("set", f"network.{br_sec}.type=bridge")
            self._uci("set", f"network.{br_sec}.proto=static")
            if brcfg.get("vlan-aware"):
                self._uci("set", f"network.{br_sec}.vlan_filtering=1")
            for port in brcfg.get("port") or []:
                self._uci("add_list", f"network.{br_sec}.ports={port}")
            # vlan entries
            for vid, vcfg in (brcfg.get("vlan") or {}).items():
                if not isinstance(vcfg, dict):
                    continue
                vsec = f"vyos_br_{brname}_vlan{vid}"
                self._uci("set", f"network.{vsec}=bridge-vlan")
                self._uci("set", f"network.{vsec}.device={brname}")
                self._uci("set", f"network.{vsec}.vlan={vid}")
                for p in vcfg.get("untagged") or []:
                    self._uci("add_list", f"network.{vsec}.ports={p}:u*")
                for p in vcfg.get("tagged") or []:
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
            subprocess.run(["uci", "apply"], capture_output=True, timeout=10)
            return [f"hostname -> {new_h}"]
        except Exception as e:  # noqa: BLE001
            return [f"hostname apply failed: {e}"]

    def _apply_name_servers(self, old: Dict[str, Any], new: Dict[str, Any]) -> List[str]:
        old_dns = (old.get("system") or {}).get("name-server") or []
        new_dns = (new.get("system") or {}).get("name-server") or []
        if list(old_dns) == list(new_dns):
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
            notes.append(f"dns servers -> {', '.join(new_dns)}")
            # domain-search
            new_search = (new.get("system") or {}).get("domain-search") or []
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
        old_dns = (old.get("system") or {}).get("dns") or []
        new_dns = (new.get("system") or {}).get("dns") or []
        if list(old_dns) == list(new_dns):
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
            notes.append(f"system resolver -> {', '.join(new_dns) or '(cleared)'}")
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
            old_ntp = list(old_s.get("ntp") or [])
            new_ntp = list(new_s.get("ntp") or [])
            if old_ntp != new_ntp:
                self._uci("set", "system.ntp.enabled=1")
                self._uci("set", "system.ntp.enable_server=0")
                try:
                    self._uci("delete", "system.ntp.server")
                except subprocess.CalledProcessError:
                    pass
                for srv in new_ntp:
                    self._uci("add_list", f"system.ntp.server={srv}")
                notes.append(f"ntp servers -> {', '.join(new_ntp)}")
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

    def _apply_nat(self, old, new):
        old_n = old.get("nat") or {}
        new_n = new.get("nat") or {}
        if old_n == new_n:
            return []
        notes = []
        try:
            # wipe old vyos nat sections
            out = self._uci("show", "firewall").stdout
            for line in out.splitlines():
                if line.startswith("firewall.vyos_nat_"):
                    sec = line.split(".")[1].split("=")[0]
                    try:
                        self._uci("delete", f"firewall.{sec}")
                    except subprocess.CalledProcessError:
                        pass
            # source NAT
            for rid, rule in (new_n.get("source") or {}).items():
                s = f"vyos_nat_src_{rid}"
                self._uci("set", f"firewall.{s}=nat")
                self._uci("set", f"firewall.{s}.name=vyos_src_{rid}")
                self._uci("set", f"firewall.{s}.target=MASQUERADE")
                if rule.get("out-interface"):
                    # map interface name to OpenWrt zone guess: wan
                    self._uci("set", f"firewall.{s}.src=lan")
                    self._uci("set", f"firewall.{s}.dest={rule['out-interface']}")
            # destination NAT (port forward)
            for rid, rule in (new_n.get("destination") or {}).items():
                s = f"vyos_nat_dst_{rid}"
                self._uci("set", f"firewall.{s}=nat")
                self._uci("set", f"firewall.{s}.name=vyos_dst_{rid}")
                self._uci("set", f"firewall.{s}.target=DNAT")
                self._uci("set", f"firewall.{s}.src=wan")
                if rule.get("port"):
                    self._uci("set", f"firewall.{s}.dst_dport={rule['port']}")
                if rule.get("to"):
                    self._uci("set", f"firewall.{s}.to_dest={rule['to']}")
            self._uci("commit", "firewall")
            subprocess.run(["/etc/init.d/firewall", "reload"],
                           capture_output=True, text=True, timeout=15)
            notes.append(f"nat: {len(new_n.get('source') or {})} source, {len(new_n.get('destination') or {})} dst rules")
        except Exception as e:
            notes.append(f"nat apply failed: {e}")
        return notes

    def _apply_wireguard(self, old: Dict[str, Any], new: Dict[str, Any]) -> List[str]:
        old_wg = (old.get("interfaces") or {}).get("wireguard") or {}
        new_wg = (new.get("interfaces") or {}).get("wireguard") or {}
        if old_wg == new_wg:
            return []
        notes = []
        try:
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
                for a in cfg.get("address") or []:
                    self._uci("add_list", f"network.{ifname}.addresses={a}")
                # peers
                pfx = f"peer_{ifname}_"
                for pk, peer in (cfg.get("peer") or {}).items():
                    if not isinstance(peer, dict):
                        continue
                    slug = pk[:20].replace("/", "_").replace("+", "_")
                    ps = f"{pfx}{slug}"
                    self._uci("set", f"network.{ps}=wireguard_{ifname}")
                    self._uci("set", f"network.{ps}.public_key={pk}")
                    if peer.get("endpoint"):
                        self._uci("set", f"network.{ps}.endpoint_host={peer['endpoint']}")
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
                for p in cfg.get("push") or []:
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

    def _apply_bgp(self, old, new):
        old_b = (old.get("protocols") or {}).get("bgp") or {}
        new_b = (new.get("protocols") or {}).get("bgp") or {}
        if old_b == new_b:
            return []
        notes = []
        try:
            # wipe old vyos sections
            out = self._uci("show", "frr").stdout
            for line in out.splitlines():
                if line.startswith("frr.vyos_"):
                    sec = line.split(".")[1].split("=")[0]
                    try:
                        self._uci("delete", f"frr.{sec}")
                    except subprocess.CalledProcessError:
                        pass
            if new_b.get("local-as"):
                self._uci("set", "frr.vyos_bgp=bgp")
                self._uci("set", f"frr.vyos_bgp.asn={new_b['local-as']}")
                if new_b.get("router-id"):
                    self._uci("set", f"frr.vyos_bgp.router_id={new_b['router-id']}")
                for ip, nb in (new_b.get("neighbor") or {}).items():
                    if not isinstance(nb, dict):
                        continue
                    s = f"vyos_bgp_nb_{ip.replace('.', '_').replace(':', '_')}"
                    self._uci("set", f"frr.{s}=bgp_neighbor")
                    self._uci("set", f"frr.{s}.peer_ip={ip}")
                    if nb.get("remote-as"):
                        self._uci("set", f"frr.{s}.peer_asn={nb['remote-as']}")
                    if nb.get("description"):
                        self._uci("set", f"frr.{s}.description={nb['description']}")
                for pgname, pg in (new_b.get("peer-group") or {}).items():
                    if not isinstance(pg, dict):
                        continue
                    s = f"vyos_bgp_pg_{pgname}"
                    self._uci("set", f"frr.{s}=bgp_peer_group")
                    self._uci("set", f"frr.{s}.peer_group={pgname}")
                    if pg.get("remote-as"):
                        self._uci("set", f"frr.{s}.peer_asn={pg['remote-as']}")
                    if pg.get("update-source"):
                        self._uci("set", f"frr.{s}.update_source={pg['update-source']}")
                    if pg.get("route-map-import"):
                        self._uci("set", f"frr.{s}.route_map_in={pg['route-map-import']}")
                for ip, nb in (new_b.get("neighbor") or {}).items():
                    if not isinstance(nb, dict):
                        continue
                    if nb.get("peer-group"):
                        s = f"vyos_bgp_nb_{ip.replace('.', '_').replace(':', '_')}"
                        self._uci("set", f"frr.{s}=bgp_neighbor")
                        self._uci("set", f"frr.{s}.peer_ip={ip}")
                        self._uci("set", f"frr.{s}.peer_group={nb['peer-group']}")
                for net in new_b.get("network") or []:
                    s = f"vyos_bgp_net_{net.replace('/', '_').replace('.', '_')}"
                    self._uci("set", f"frr.{s}=bgp_network")
                    self._uci("set", f"frr.{s}.prefix={net}")
            self._uci("commit", "frr")
            # append route-maps to frr.conf (FRR UCI route-map support is weak)
            rmaps = (new.get("protocols") or {}).get("route-map") or {}
            conf = "/etc/frr/frr.conf"
            try:
                old_conf = open(conf).read()
            except Exception:
                old_conf = ""
            # strip old marked block
            import re
            old_conf = re.sub(r"# --- vyoscli:route-map:begin ---.*?# --- vyoscli:route-map:end ---\n?", "", old_conf, flags=re.S)
            # community-list
            comlists = (new.get("policy") or {}).get("community-list") or {}
            block = []
            if rmaps or comlists:
                block.append("# --- vyoscli:route-map:begin ---")
                for clnum, clbody in comlists.items():
                    if not isinstance(clbody, dict):
                        continue
                    for ruleno, rule in (clbody or {}).items():
                        regex = (rule or {}).get("regex", "")
                        block.append(f"bgp community-list {clnum} permit {regex}")
                for name, body in rmaps.items():
                    if not isinstance(body, dict):
                        continue
                    for action, rules in body.items():
                        for ruleno, rbody in (rules or {}).items():
                            sets = (rbody or {}).get("set") or {}
                            matches = (rbody or {}).get("match") or {}
                            block.append(f"route-map {name} {action} {ruleno}")
                            for k, v in matches.items():
                                block.append(f"  match {k.replace('-', ' ')} {v}")
                            for k, v in sets.items():
                                block.append(f"  set {k.replace('-', ' ')} {v}")
                block.append("# --- vyoscli:route-map:end ---")
            new_conf = old_conf.rstrip() + "\n" + "\n".join(block) + "\n"
            try:
                open(conf, "w").write(new_conf)
            except Exception:
                pass
            # decide hot reload vs restart
            old_bgp_core = {k: v for k, v in old_b.items() if k != "route-map"}
            new_bgp_core = {k: v for k, v in new_b.items() if k != "route-map"}
            if old_bgp_core != new_bgp_core:
                # core config changed, need restart
                subprocess.run(["/etc/init.d/frr", "restart"],
                               capture_output=True, text=True, timeout=20)
                notes.append(f"bgp: restarted, AS{new_b.get('local-as')}, {len(new_b.get('neighbor') or {})} peers")
            else:
                # route-map only: hot reload via vtysh
                # no old route-maps
                old_rmaps = (old.get("protocols") or {}).get("route-map") or {}
                for name in old_rmaps:
                    subprocess.run(["vtysh", "-c", "configure terminal",
                                    "-c", f"no route-map {name}"],
                                   capture_output=True, text=True, timeout=5)
                for line in block:
                    if line.startswith("#"):
                        continue
                    cmd = line.strip()
                    if not cmd:
                        continue
                    subprocess.run(["vtysh", "-c", "configure terminal",
                                    "-c", cmd],
                                   capture_output=True, text=True, timeout=5)
                notes.append(f"bgp: route-maps hot-loaded ({len(rmaps)})")
        except Exception as e:
            notes.append(f"bgp apply failed: {e}")
        return notes

    def _apply_interface_roles(self, old: Dict[str, Any], new: Dict[str, Any]) -> List[str]:
        old_if = old.get("interfaces") or {}
        new_if = new.get("interfaces") or {}
        notes = []
        try:
            # ---- wan/lan role ----
            old_role = old_if.get("role") or {}
            new_role = new_if.get("role") or {}
            if old_role != new_role:
                for role, dev in new_role.items():
                    self._uci("set", f"network.{role}=interface")
                    self._uci("set", f"network.{role}.device={dev}")
                    if role == "wan":
                        self._uci("set", f"network.{role}.proto=dhcp")
                    else:
                        self._uci("set", f"network.{role}.proto=static")
                notes.append(f"interface roles: {new_role}")
            # ---- bridge ----
            old_br = old_if.get("bridge") or {}
            new_br = new_if.get("bridge") or {}
            if old_br != new_br:
                for br, ports in new_br.items():
                    self._uci("set", f"network.{br}=interface")
                    self._uci("set", f"network.{br}.type=bridge")
                    self._uci("set", f"network.{br}.proto=static")
                    try:
                        self._uci("delete", f"network.{br}.ports")
                    except subprocess.CalledProcessError:
                        pass
                    for p in ports or []:
                        self._uci("add_list", f"network.{br}.ports={p}")
                notes.append(f"bridges: {list(new_br.keys())}")
            # ---- dummy ----
            old_dm = old_if.get("dummy") or {}
            new_dm = new_if.get("dummy") or {}
            if old_dm != new_dm:
                for dm, cfg in new_dm.items():
                    self._uci("set", f"network.{dm}=interface")
                    self._uci("set", f"network.{dm}.proto=static")
                    if isinstance(cfg, dict) and cfg.get("address"):
                        self._uci("set", f"network.{dm}.ipaddr={cfg['address']}")
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
        notes = []
        try:
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
            # Main smartdns section.
            enabled = 1 if new_sd.get("enabled") else 0
            self._uci("set", "smartdns.cfg_vyos_main=smartdns")
            self._uci("set", f"smartdns.cfg_vyos_main.enabled={enabled}")
            self._uci("set", f"smartdns.cfg_vyos_main.port={new_sd.get('port', 5333)}")
            scm = new_sd.get("speed-check-mode", "")
            if scm:
                self._uci("set", f"smartdns.cfg_vyos_main.speed_check_mode={scm}")
            # forbid-aaaa -> force_aaaa=0 (disable AAAA replies)
            self._uci("set",
                      f"smartdns.cfg_vyos_main.force_aaaa={0 if new_sd.get('forbid-aaaa') else 1}")
            # upstreams
            for name, cfg in (new_sd.get("server") or {}).items():
                if not isinstance(cfg, dict):
                    continue
                s = f"vyos_srv_{name}"
                self._uci("set", f"smartdns.{s}=server")
                self._uci("set", f"smartdns.{s}.name={name}")
                if cfg.get("ip"):
                    self._uci("set", f"smartdns.{s}.ip={cfg['ip']}")
                if cfg.get("port"):
                    self._uci("set", f"smartdns.{s}.port={cfg['port']}")
                if cfg.get("type"):
                    self._uci("set", f"smartdns.{s}.type={cfg['type']}")
            # domain-sets (name -> {domain: [...], file: "/path"})
            for name, cfg in (new_sd.get("domain-set") or {}).items():
                if not isinstance(cfg, dict):
                    continue
                s = f"vyos_dset_{name}"
                self._uci("set", f"smartdns.{s}=domain-set")
                self._uci("set", f"smartdns.{s}.name={name}")
                if cfg.get("file"):
                    self._uci("set", f"smartdns.{s}.domain_file={cfg['file']}")
                for d in cfg.get("domain") or []:
                    self._uci("add_list", f"smartdns.{s}.domain={d}")
            # domain-rules
            for name, cfg in (new_sd.get("domain-rule") or {}).items():
                if not isinstance(cfg, dict):
                    continue
                s = f"vyos_drule_{name}"
                self._uci("set", f"smartdns.{s}=domain-rule")
                if cfg.get("domain-set"):
                    self._uci("set", f"smartdns.{s}.domain-set={cfg['domain-set']}")
                for fwd in cfg.get("forward") or []:
                    self._uci("add_list", f"smartdns.{s}.forward={fwd}")
            # static addresses (intranet hosts)
            for domain, cfg in (new_sd.get("address") or {}).items():
                if not isinstance(cfg, dict):
                    continue
                slug = domain.replace(".", "_").replace(":", "_")
                s = f"vyos_addr_{slug}"
                self._uci("set", f"smartdns.{s}=address")
                self._uci("set", f"smartdns.{s}.domain={domain}")
                if cfg.get("ip"):
                    self._uci("set", f"smartdns.{s}.address={cfg['ip']}")
            self._uci("commit", "smartdns")
            subprocess.run(["/etc/init.d/smartdns", "restart"],
                           capture_output=True, text=True, timeout=15)
            notes.append(f"smartdns {'enabled' if enabled else 'disabled'} on port {new_sd.get('port', 5333)}")
        except Exception as e:  # noqa: BLE001
            notes.append(f"smartdns apply failed: {e} (is the smartdns package installed?)")
        return notes

    def _apply_crontab(self, old: Dict[str, Any], new: Dict[str, Any]) -> List[str]:
        old_cron = (old.get("service") or {}).get("crontab") or {}
        new_cron = (new.get("service") or {}).get("crontab") or {}
        if old_cron == new_cron:
            return []
        notes = []
        tab_path = "/etc/crontabs/root"
        try:
            # Keep user-authored lines (outside our block markers).
            existing = ""
            if os.path.exists(tab_path):
                with open(tab_path, encoding="utf-8") as f:
                    existing = f.read()
            lines = [ln for ln in existing.splitlines()
                     if "--- vyoscli:" not in ln]
            # strip trailing empty lines
            while lines and not lines[-1].strip():
                lines.pop()
            # append our managed blocks
            for name, cfg in new_cron.items():
                if not isinstance(cfg, dict):
                    continue
                sched = cfg.get("schedule")
                script = cfg.get("script")
                desc = cfg.get("description", "")
                if not sched or not script:
                    continue
                lines.append(f"# --- vyoscli:begin:{name} ---")
                if desc:
                    lines.append(f"# {desc}")
                lines.append(f"{sched} {script}")
                lines.append(f"# --- vyoscli:end:{name} ---")
            with open(tab_path, "w", encoding="utf-8") as f:
                f.write("\n".join(lines) + "\n")
            os.chmod(tab_path, 0o600)
            subprocess.run(["/etc/init.d/cron", "restart"],
                           capture_output=True, text=True, timeout=10)
            notes.append(f"crontab: {len(new_cron)} managed job(s) written")
        except Exception as e:  # noqa: BLE001
            notes.append(f"crontab apply failed: {e}")
        return notes

    def _apply_dhcp(self, old: Dict[str, Any], new: Dict[str, Any]) -> List[str]:
        old_d = (old.get("service") or {}).get("dhcp") or {}
        new_d = (new.get("service") or {}).get("dhcp") or {}
        if old_d == new_d:
            return []
        notes = []
        try:
            for name, cfg in new_d.items():
                if not isinstance(cfg, dict):
                    continue
                s = f"vyos_dhcp_{name}"
                subnet = cfg.get("subnet", "")
                interface = cfg.get("interface", name)
                self._uci("set", f"dhcp.{s}=dhcp")
                self._uci("set", f"dhcp.{s}.interface={interface}")
                self._uci("set", f"dhcp.{s}.dhcpv4=server")
                # range
                rs = cfg.get("range-start", "")
                re_ = cfg.get("range-end", "")
                if rs and re_:
                    try:
                        host_start = int(rs.split(".")[-1])
                        host_end = int(re_.split(".")[-1])
                        limit = max(1, host_end - host_start + 1)
                        self._uci("set", f"dhcp.{s}.start={host_start}")
                        self._uci("set", f"dhcp.{s}.limit={limit}")
                    except ValueError:
                        pass
                # options
                try:
                    self._uci("delete", f"dhcp.{s}.dhcp_option")
                except subprocess.CalledProcessError:
                    pass
                if cfg.get("gateway"):
                    self._uci("add_list", f"dhcp.{s}.dhcp_option=router,{cfg['gateway']}")
                for d in cfg.get("dns") or []:
                    self._uci("add_list", f"dhcp.{s}.dhcp_option=option:dns,{d}")
                if cfg.get("domain"):
                    self._uci("add_list", f"dhcp.{s}.dhcp_option=option:domain,{cfg['domain']}")
                if cfg.get("domain-search"):
                    self._uci("add_list", f"dhcp.{s}.dhcp_option=option:domain-search,{cfg['domain-search']}")
                if cfg.get("wpad-url"):
                    self._uci("add_list", f"dhcp.{s}.dhcp_option=option:252,{cfg['wpad-url']}")
                # static leases
                for sname, scfg in (cfg.get("static-mapping") or {}).items():
                    if not isinstance(scfg, dict):
                        continue
                    hs = f"vyos_dhcp_host_{name}_{sname}"
                    self._uci("set", f"dhcp.{hs}=host")
                    self._uci("set", f"dhcp.{hs}.name={sname}")
                    self._uci("set", f"dhcp.{hs}.mac={scfg.get('mac', '')}")
                    self._uci("set", f"dhcp.{hs}.ip={scfg.get('ip-address', '')}")
            self._uci("commit", "dhcp")
            subprocess.run(["/etc/init.d/dnsmasq", "reload"],
                           capture_output=True, text=True, timeout=10)
            notes.append(f"dhcp: {len(new_d)} subnet(s) configured")
        except Exception as e:  # noqa: BLE001
            notes.append(f"dhcp apply failed: {e}")
        return notes

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
            # UCI /etc/config/adguardhome
            self._uci("set", "adguardhome.main=adguardhome")
            self._uci("set", f"adguardhome.main.enabled={'1' if new_ag.get('enabled') else '0'}")
            if new_ag.get("port"):
                self._uci("set", f"adguardhome.main.listen_port={new_ag['port']}")
            if new_ag.get("web-port"):
                self._uci("set", f"adguardhome.main.web_port={new_ag['web-port']}")
            self._uci("commit", "adguardhome")
            subprocess.run(["/etc/init.d/adguardhome", "restart"],
                           capture_output=True, text=True, timeout=15)
            if new_ag.get("enabled"):
                notes.append(f"adguardhome: enabled on DNS port {new_ag.get('port',53)}, web :{new_ag.get('web-port',3000)}")
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
                # root qdisc
                subprocess.run(["tc", "qdisc", "add", "dev", iface, "root", "handle", "1:", "htb", "default", "10"],
                               capture_output=True, timeout=5)
                # default class
                subprocess.run(["tc", "class", "add", "dev", iface, "parent", "1:", "classid", "1:10",
                                "htb", "rate", bandwidth, "ceil", bandwidth],
                               capture_output=True, timeout=5)
                notes.append(f"qos {name}: {iface} total={bandwidth}, per-ip={per_ip}")
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
            iface = new_sqm.get("interface", "eth0")
            download = new_sqm.get("download", 100000)
            upload = new_sqm.get("upload", 10000)
            qdisc = new_sqm.get("qdisc", "cake")
            # create sections if missing
            try:
                self._uci("get", "sqm.@general[0]")
            except subprocess.CalledProcessError:
                self._uci("add", "sqm", "general")
            try:
                self._uci("get", "sqm.@queue[0]")
            except subprocess.CalledProcessError:
                self._uci("add", "sqm", "queue")
            self._uci("set", "sqm.@general[0].enabled=1")
            self._uci("set", f"sqm.@queue[0].interface={iface}")
            self._uci("set", f"sqm.@queue[0].download={download}")
            self._uci("set", f"sqm.@queue[0].upload={upload}")
            self._uci("set", f"sqm.@queue[0].qdisc={qdisc}")
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
                open(f"/etc/init.d/kcp_{name}", "w").write(conf)
                subprocess.run(["chmod", "+x", f"/etc/init.d/kcp_{name}"],
                               capture_output=True, timeout=5)
                subprocess.run(["/etc/init.d", f"kcp_{name}", "restart"],
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
            if new_tcp.get("fq_codel", True):
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

    def _apply_login(self, old, new):
        old_login = (old.get("system") or {}).get("login") or {}
        new_login = (new.get("system") or {}).get("login") or {}
        if old_login == new_login:
            return []
        notes = []
        try:
            for name, u in (new_login.get("user") or {}).items():
                if not isinstance(u, dict):
                    continue
                # create user if not exists
                subprocess.run(["id", name], capture_output=True, timeout=5)
                if subprocess.run(["id", name], capture_output=True, timeout=5).returncode != 0:
                    subprocess.run(["useradd", "-m", "-s", "/bin/ash", name],
                                   capture_output=True, timeout=5)
                # password
                pwd = u.get("password")
                if pwd:
                    subprocess.run(["chpasswd"], input=f"{name}:{pwd}\n",
                                   text=True, capture_output=True, timeout=5)
                # disable
                if u.get("disable"):
                    subprocess.run(["usermod", "-L", name], capture_output=True, timeout=5)
                else:
                    subprocess.run(["usermod", "-U", name], capture_output=True, timeout=5)
                # ssh keys
                keys = u.get("public-keys") or {}
                if keys:
                    ssh_dir = f"/home/{name}/.ssh"
                    subprocess.run(["mkdir", "-p", ssh_dir], capture_output=True, timeout=5)
                    lines = []
                    for kid, k in keys.items():
                        if isinstance(k, dict) and k.get("key"):
                            ktype = k.get("type", "ssh-rsa")
                            lines.append(f"{ktype} {k['key']} {kid}")
                    open(f"{ssh_dir}/authorized_keys", "w").write("\n".join(lines) + "\n")
                    subprocess.run(["chmod", "600", f"{ssh_dir}/authorized_keys"],
                                   capture_output=True, timeout=5)
                    subprocess.run(["chown", "-R", name, ssh_dir], capture_output=True, timeout=5)
            notes.append(f"login: {len(new_login.get('user') or {})} users")
        except Exception as e:
            notes.append(f"login apply failed: {e}")
        return notes

    def _apply_ipsec(self, old, new):
        old_ip = (old.get("vpn") or {}).get("ipsec") or {}
        new_ip = (new.get("vpn") or {}).get("ipsec") or {}
        if old_ip == new_ip:
            return []
        notes = []
        try:
            # write ipsec.conf
            conf = ["# managed by vyoscli", "config setup:"]
            for ike_name, ike in (new_ip.get("ike-group") or {}).items():
                conf.append(f"conn {ike_name}")
                conf.append(f"  keyexchange=ikev2")
                conf.append(f"  lifetime={ike.get('lifetime', 28800)}s")
                props = []
                for pnum, p in (ike.get("proposal") or {}).items():
                    props.append(f"{p.get('encryption','aes256')}-{p.get('hash','sha256')}-modp{p.get('dh-group',14)*256}")
                conf.append(f"  ike={';'.join(props)}")
            for esp_name, esp in (new_ip.get("esp-group") or {}).items():
                conf.append(f"conn {esp_name}")
                props = []
                for pnum, p in (esp.get("proposal") or {}).items():
                    props.append(f"{p.get('encryption','aes256')}-{p.get('hash','sha256')}")
                conf.append(f"  esp-proposals={';'.join(props)}")
                conf.append(f"  lifetime={esp.get('lifetime', 3600)}s")
            ra = new_ip.get("remote-access") or {}
            if ra.get("enabled"):
                conf.append("conn remote-access")
                conf.append(f"  left={ra.get('local-address','%any')}")
                conf.append(f"  leftid={ra.get('local-id','')}")
                conf.append("  leftauth=psk")
                conf.append("  right=%any")
                conf.append("  rightauth=psk")
                conf.append(f"  rightsourceip={ra.get('pool-start','10.100.0.10')}-{ra.get('pool-end','10.100.0.100')}")
                dns = ra.get("dns") or []
                if dns:
                    conf.append(f"  rightdns={','.join(dns)}")
                conf.append("  auto=add")
            for peer_ip, peer in (new_ip.get("peer") or {}).items():
                conf.append(f"conn peer-{peer_ip}")
                conf.append(f"  left={peer.get('local-address', '0.0.0.0')}")
                conf.append(f"  leftid={peer.get('local-id', peer.get('local-address',''))}")
                conf.append(f"  right={peer.get('remote-address', peer_ip)}")
                conf.append(f"  rightid={peer.get('remote-id', '')}")
                conf.append(f"  auto=start")
                conf.append(f"  ike={peer.get('ike-group','')}")
                conf.append(f"  esp={peer.get('esp-group','')}")
                for tnum, tun in (peer.get("tunnel") or {}).items():
                    conf.append(f"  leftsubnet={tun.get('local-prefix','0.0.0.0/0')}")
                    conf.append(f"  rightsubnet={tun.get('remote-prefix','0.0.0.0/0')}")
            open("/etc/ipsec.conf", "w").write("\n".join(conf) + "\n")
            # write ipsec.secrets
            secrets = []
            ra = new_ip.get("remote-access") or {}
            if ra.get("enabled"):
                conf.append("conn remote-access")
                conf.append(f"  left={ra.get('local-address','%any')}")
                conf.append(f"  leftid={ra.get('local-id','')}")
                conf.append("  leftauth=psk")
                conf.append("  right=%any")
                conf.append("  rightauth=psk")
                conf.append(f"  rightsourceip={ra.get('pool-start','10.100.0.10')}-{ra.get('pool-end','10.100.0.100')}")
                dns = ra.get("dns") or []
                if dns:
                    conf.append(f"  rightdns={','.join(dns)}")
                conf.append("  auto=add")
            for peer_ip, peer in (new_ip.get("peer") or {}).items():
                sec = peer.get("secret")
                if sec:
                    secrets.append(f"{peer.get('local-address','')} {peer.get('remote-address',peer_ip)} : PSK \"{sec}\"")
            open("/etc/ipsec.secrets", "w").write("\n".join(secrets) + "\n")
            subprocess.run(["/etc/init.d/ipsec", "restart"],
                           capture_output=True, text=True, timeout=15)
            notes.append(f"ipsec: {len(new_ip.get('peer') or {})} peers")
        except Exception as e:
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
            open("/etc/conserver/conserver.cf", "w").write("\n".join(cf) + "\n")
            subprocess.run(["/etc/init.d/conserver", "restart"],
                           capture_output=True, text=True, timeout=10)
            # start dropbear per-device
            # kill old per-device dropbear pids
            try:
                import glob
                for pidfile in glob.glob("/var/run/vyoscli-console-*.pid"):
                    subprocess.run(["kill", "$(cat " + pidfile + ")"],
                                   shell=True, capture_output=True, timeout=5)
                    import os
                    os.remove(pidfile)
            except Exception:
                pass
            for dev, cfg in new_cs.items():
                port = cfg.get("ssh-port")
                if not port:
                    continue
                pidfile = f"/var/run/vyoscli-console-{dev}.pid"
                subprocess.Popen([
                    "/usr/sbin/dropbear", "-j", "-k",
                    "-r", "/etc/dropbear/dropbear_rsa_host_key",
                    "-c", f"console {dev}",
                    "-P", pidfile,
                    "-p", str(port)
                ])
                notes.append(f"console {dev}: port {port} baud {cfg.get('speed',9600)}")
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
            "dhcp": "dnsmasq",
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
                for p in cfg.get("port") or []:
                    cmd += ["-p", p]
                for v in cfg.get("volume") or []:
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
        with open(self.rollback_conf, "w", encoding="utf-8") as f:
            json.dump({"pid": proc.pid,
                       "deadline": time.time() + seconds,
                       "snapshot": snapshot_path}, f)
        return proc.pid

    def disarm_rollback_timer(self) -> Optional[int]:
        if not os.path.exists(self.rollback_conf):
            return None
        with open(self.rollback_conf, encoding="utf-8") as f:
            conf = json.load(f)
        pid = conf.get("pid")
        try:
            os.kill(pid, 15)
        except Exception:
            pass
        os.remove(self.rollback_conf)
        return pid

    def pending_rollback(self) -> Optional[Dict[str, Any]]:
        if not os.path.exists(self.rollback_conf):
            return None
        with open(self.rollback_conf, encoding="utf-8") as f:
            return json.load(f)

    # ---------- commit / confirm / rollback ----------
    def commit(self, confirmed_minutes: int = 0) -> str:
        if not self.modified():
            return "No changes to commit."
        snapshot = self._snapshot_current_running()
        old_running = copy.deepcopy(self.running)
        self.running = copy.deepcopy(self.candidate)
        # DNS port conflict guard
        conflicts = self._check_dns_conflicts(self.running)
        if conflicts:
            # roll back running to old so candidate stays dirty
            self.running = old_running
            self._dump(self.running_path, self.running)
            return "Commit aborted: " + "; ".join(conflicts)
        self._dump(self.running_path, self.running)
        notes = self._apply_all(old_running, self.running)

        out = "Commit complete."
        if confirmed_minutes > 0:
            pid = self.arm_rollback_timer(confirmed_minutes * 60, snapshot)
            out += (f" Auto-rollback armed for {confirmed_minutes} min "
                    f"(pid {pid}). Run 'commit confirm' to keep these changes.")
        for n in notes:
            out += f"\n  - {n}"
        return out

    def confirm(self) -> str:
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
        notes = self._apply_all(old_running, self.running)
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
        return "Saved to /etc/vyoscli/running.json"

    # ---------- rendering ----------
    def render_set_commands(self, cfg: Optional[Dict[str, Any]] = None, prefix: List[str] = None) -> List[str]:
        cfg = cfg if cfg is not None else self.candidate
        prefix = prefix or []
        out: List[str] = []
        if isinstance(cfg, dict):
            for k in sorted(cfg.keys()):
                v = cfg[k]
                if isinstance(v, dict):
                    out.extend(self.render_set_commands(v, prefix + [k]))
                elif isinstance(v, list):
                    for item in v:
                        out.append("set " + " ".join(prefix + [k, str(item)]))
                else:
                    out.append("set " + " ".join(prefix + [k, str(v)]))
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
            if isinstance(v, dict):
                lines.append(f"{pad}{k} {{")
                lines.append(self.render_tree(v, indent + 1))
                lines.append(f"{pad}}}")
            elif isinstance(v, list):
                for item in v:
                    lines.append(f"{pad}{k} {item}")
            else:
                lines.append(f"{pad}{k} {v}")
        return "\n".join(lines)
