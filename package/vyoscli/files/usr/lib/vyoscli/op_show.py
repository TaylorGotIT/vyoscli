"""op 模式命令函数 - show 类"""
import os
from typing import Any


REQUIRED_PACKAGES = [
    ("python3", "python3"),
    ("python3-readline", "python3-readline"),
    ("ip-full", "ip"),
    ("smartdns", "smartdns"),
    ("adguardhome", "AdGuardHome"),
    ("frr", "vtysh"),
    ("kmod-tcp-bbr", "kmod-tcp-bbr"),
    ("kmod-tcp-hybla", "kmod-tcp-hybla"),
    ("kmod-wireguard", "wg"),
    ("wireguard-tools", "wg"),
    ("openvpn-openssl", "openvpn"),
    ("strongswan-minimal", "ipsec"),
    ("conserver", "conserver"),
    ("podman", "podman"),
    ("kmod-gre", "kmod-gre"),
    ("kmod-ipip", "kmod-ipip"),
    ("kmod-vxlan", "kmod-vxlan"),
    ("tc", "tc"),
    ("sqm-scripts", "sqm"),
]


def _op_show_dependencies(ctx: Any, value: Any) -> str:
    import shutil
    import subprocess
    out = ["Package Status:"]
    out.append(f"{'Package':<25} {'Status':<10}")
    out.append(f"{'-'*25} {'-'*10}")
    missing = []
    for pkg, bin_name in REQUIRED_PACKAGES:
        # Check if installed via opkg
        r = subprocess.run(["opkg", "list-installed", pkg], capture_output=True, text=True, timeout=5)
        installed = pkg in r.stdout
        if installed:
            status = "OK"
        else:
            status = "MISSING"
            missing.append(pkg)
        out.append(f"{pkg:<25} {status:<10}")
    out.append("")
    if missing:
        out.append(f"Missing: {', '.join(missing)}")
        out.append("Install with:")
        out.append(f"  opkg install {' '.join(missing)}")
    else:
        out.append("All dependencies installed.")
    return "\n".join(out)


def _op_show_log(ctx: Any, value: Any) -> str:
    import subprocess
    try:
        r = subprocess.run(["logread"], capture_output=True, text=True, timeout=10)
        return r.stdout or r.stderr or "(empty log)"
    except Exception as e:
        return f"logread failed: {e}"


def _op_show_history(ctx: Any, value: Any) -> str:
    import readline
    n = readline.get_current_history_length()
    if n == 0:
        return "No history."
    out = []
    for i in range(1, n + 1):
        out.append(f"  {i:4d}  {readline.get_history_item(i)}")
    return "\n".join(out)


def _op_show_version(ctx: Any, value: Any) -> str:
    import platform
    uname = platform.uname()
    sys_cfg = ctx.store.get(["system"], candidate=False) or {}
    host = sys_cfg.get("host-name", "OpenWrt")
    hw = sys_cfg.get("hardware") or {}

    def _read(path: str) -> str:
        try:
            with open(path, encoding="utf-8") as f:
                return f.read().strip()
        except Exception:
            return ""

    openwrt_ver = _read("/etc/openwrt_release")
    for line in openwrt_ver.splitlines():
        if line.startswith("DISTRIB_DESCRIPTION="):
            openwrt_ver = line.split("=", 1)[1].strip().strip("'\"")
            break
    else:
        openwrt_ver = uname.release

    return (
        f"Hostname:          {host}\n"
        f"OS:                {openwrt_ver}\n"
        f"Kernel:            {uname.release} {uname.machine}\n"
        f"Hardware vendor:   {hw.get('vendor') or '-'}\n"
        f"Hardware model:    {hw.get('model') or '-'}\n"
        f"Hardware serial:   {hw.get('serial') or '-'}\n"
    )


def _op_show_configuration(ctx: Any, value: Any) -> str:
    return ctx.store.render_tree(ctx.store.get([], candidate=False))


def _op_show_configuration_commands(ctx: Any, value: Any) -> str:
    return "\n".join(ctx.store.render_set_commands(ctx.store.get([], candidate=False)))


def _op_show_configuration_json(ctx: Any, value: Any) -> str:
    import json
    return json.dumps(ctx.store.get([], candidate=False), indent=2)


def _op_show_interfaces(ctx: Any, value: Any) -> str:
    import subprocess

    # Configured interfaces come from the running config; kernel-only
    # pseudo devices (gre0, gretap0, dummy0, tunl0, ...) must not show up.
    ifaces = ctx.store.get(["interfaces"], candidate=False) or {}
    configured = {}
    for items in ifaces.values():
        if not isinstance(items, dict):
            continue
        for name, cfg in items.items():
            if not isinstance(cfg, dict):
                continue
            addrs = cfg.get("address")
            if isinstance(addrs, str):
                addrs = [addrs]
            configured[name] = (cfg.get("description") or "", addrs or [])

    try:
        link_out = subprocess.run(["ip", "-o", "link"], capture_output=True,
                                  text=True, timeout=5).stdout
    except Exception:
        link_out = ""
    link_map = {}
    for line in link_out.splitlines():
        parts = line.split()
        if len(parts) < 4:
            continue
        iface = parts[1].rstrip(":").split("@", 1)[0]
        flags = ""
        if "<" in line and ">" in line:
            flags = line.split("<", 1)[1].split(">", 1)[0]
        admin = "u" if "UP" in flags.split(",") else "D"
        oper = "D"
        for i, p in enumerate(parts):
            if p == "state" and i + 1 < len(parts):
                oper = "u" if parts[i + 1] in ("UP", "UNKNOWN") else "D"
                break
        mac = "--"
        for i, p in enumerate(parts):
            if p == "link/ether":
                mac = parts[i + 1]
                break
        mtu = "1500"
        for i, p in enumerate(parts):
            if p == "mtu":
                mtu = parts[i + 1]
                break
        link_map[iface] = (mac, mtu, f"{admin}/{oper}")

    try:
        addr_out = subprocess.run(["ip", "-o", "addr"], capture_output=True,
                                  text=True, timeout=5).stdout
    except Exception:
        addr_out = ""
    addr_map = {}
    for line in addr_out.splitlines():
        parts = line.split()
        if len(parts) < 4:
            continue
        iface = parts[1].split("@", 1)[0]
        for i, p in enumerate(parts):
            if p in ("inet", "inet6"):
                addr_map.setdefault(iface, []).append(parts[i + 1])
                break

    kernel_noise = {
        "gre0", "gretap0", "erspan0", "ip6gre0", "ip6gretap0", "ip6tnl0",
        "sit0", "tunl0", "ip_vti0", "ip6_vti0", "dummy0", "teql0",
        "ifb0", "ifb1", "nlmon0", "lo_unused",
    }
    physical_prefixes = ("eth", "br-", "wlan", "bat", "usb", "wwan", "ppp")

    names = list(configured)
    for name in link_map:
        if name in configured or name in kernel_noise:
            continue
        if name == "lo" or name.startswith(physical_prefixes):
            names.append(name)

    rows = []
    for name in names:
        _mac, _mtu, state = link_map.get(name, ("--", "--", "D/D"))
        addrs = addr_map.get(name) or configured.get(name, ("", []))[1]
        addr = addrs[0] if addrs else "-"
        desc = configured.get(name, ("", []))[0]
        rows.append((name, addr, state, desc))

    rows.sort(key=lambda x: (
        0 if x[0] == "lo" else
        1 if x[0].startswith("eth") else
        2 if x[0].startswith("br-") else 3,
        x[0]))

    name_w = max([len(r[0]) for r in rows] + [len("Interface")])
    addr_w = max([len(r[1]) for r in rows] + [len("IP Address")])

    lines = [
        "Codes: S - State, L - Link, u - Up, D - Down, A - Admin Down",
        "Interface".ljust(name_w + 2) +
        "IP Address".ljust(addr_w + 2) +
        "S/L".ljust(5) + "Description",
        "---------".ljust(name_w + 2) +
        "----------".ljust(addr_w + 2) +
        "---".ljust(5) + "-----------",
    ]
    for iface, addr, state, desc in rows:
        lines.append(
            iface.ljust(name_w + 2) +
            addr.ljust(addr_w + 2) +
            state.ljust(5) +
            desc
        )
    return "\n".join(lines)


def _op_show_interface_detail(ctx: Any, value: Any) -> str:
    import subprocess
    if not value:
        return "Usage: show interface ethernet <ifname>"
    try:
        r = subprocess.run(["ip", "addr", "show", value], capture_output=True, text=True, timeout=5)
        out = r.stdout.strip()
        if not out:
            return f"Interface {value} not found."
        # append only the statistics section; the full ip -s link output
        # repeats the interface header/addresses already shown above.
        try:
            s = subprocess.run(["ip", "-s", "-s", "link", "show", value],
                               capture_output=True, text=True, timeout=5)
            lines = s.stdout.splitlines()
            stats = ""
            for idx, line in enumerate(lines):
                if line.strip().startswith("RX:"):
                    stats = "\n".join(lines[idx:]).rstrip()
                    break
            if stats:
                out += "\n\n" + stats
        except Exception:
            pass
        return out
    except Exception as e:
        return f"show interface failed: {e}"


def _op_show_system_summary(ctx: Any, value: Any) -> str:
    return (
        "Possible completions:\n"
        "  uptime           Show how long the system has been up\n"
        "  memory           Show system memory usage\n"
        "  storage          Show filesystem usage\n"
        "  processes        Show running processes\n"
        "  login            Show logged-in users\n"
        "  kmsg             Show kernel messages\n"
    )


def _op_show_system_uptime(ctx: Any, value: Any) -> str:
    import subprocess
    try:
        r = subprocess.run(["uptime"], capture_output=True, text=True)
        return r.stdout.strip()
    except Exception:
        return "n/a"


def _op_show_system_memory(ctx: Any, value: Any) -> str:
    import subprocess
    try:
        r = subprocess.run(["free", "-h"], capture_output=True, text=True)
        return r.stdout.strip()
    except Exception:
        return "n/a"


def _op_show_system_storage(ctx: Any, value: Any) -> str:
    import subprocess
    try:
        r = subprocess.run(["df", "-h"], capture_output=True, text=True)
        return r.stdout.strip()
    except Exception:
        return "n/a"


def _op_show_system_processes(ctx: Any, value: Any) -> str:
    import subprocess
    try:
        r = subprocess.run(["ps", "w"], capture_output=True, text=True)
        return r.stdout.strip()
    except Exception:
        return "n/a"


def _op_show_system_kmsg(ctx: Any, value: Any) -> str:
    import subprocess
    try:
        r = subprocess.run(["dmesg"], capture_output=True, text=True, timeout=5)
        return r.stdout.strip()
    except Exception:
        return "n/a"


def _op_show_system_login(ctx: Any, value: Any) -> str:
    import subprocess
    try:
        r = subprocess.run(["w"], capture_output=True, text=True)
        return r.stdout.strip()
    except Exception:
        return "n/a"


_ROUTE_CODES = """Codes: K - kernel route, C - connected, L - local, S - static,
       R - RIP, O - OSPF, I - IS-IS, B - BGP, E - EIGRP, N - NHRP,
       T - Table, v - VNC, V - VNC-Direct, A - Babel, F - PBR,
       f - OpenFabric, t - Table-Direct,
       > - selected route, * - FIB route, q - queued, r - rejected, b - backup
       t - trapped, o - offload failure"""


def _ip_route_fallback(kind: str) -> str:
    import subprocess
    args = ["ip", "route", "show"]
    if kind == "static":
        args += ["proto", "static"]
    elif kind == "connected":
        args += ["proto", "kernel"]
    elif kind == "bgp":
        args += ["proto", "bgp"]
    try:
        return subprocess.run(args, capture_output=True, text=True,
                              timeout=10).stdout.strip() or "n/a"
    except Exception:
        return "n/a"


def _vtysh_route(command: str, fallback) -> str:
    """Prefer FRR (VyOS output); fall back to ip route when FRR is absent."""
    import shutil
    import subprocess
    if shutil.which("vtysh"):
        try:
            r = subprocess.run(["vtysh", "-c", command], capture_output=True,
                               text=True, timeout=20)
            out = (r.stdout or "").strip()
            if out and "failed to connect" not in out and "Exiting:" not in out:
                return out
        except Exception:
            pass
    return fallback()


def _op_show_ip_route(ctx: Any, value: Any) -> str:
    return _vtysh_route("show ip route",
                        lambda: _ip_route_fallback("all"))


def _vtysh_show(command: str) -> str:
    import subprocess
    try:
        r = subprocess.run(["vtysh", "-c", command], capture_output=True,
                           text=True, timeout=15)
    except FileNotFoundError:
        return "vtysh not found (install frr)"
    except Exception as e:  # noqa: BLE001
        return f"vtysh failed: {e}"
    out = (r.stdout or "").strip() or (r.stderr or "").strip()
    return out or "BGP is not running (frr/bgpd not started)"


def _op_show_arp(ctx: Any, value: Any) -> str:
    import subprocess
    try:
        out = subprocess.run(["ip", "neigh", "show"], capture_output=True,
                             text=True, timeout=5).stdout
    except Exception:
        out = ""
    rows = []
    for line in out.splitlines():
        parts = line.split()
        if not parts or ":" in parts[0]:
            continue  # IPv4 ARP only
        addr = parts[0]
        mac = ""
        iface = ""
        state = parts[-1] if parts else ""
        if "lladdr" in parts:
            mac = parts[parts.index("lladdr") + 1]
        if "dev" in parts:
            iface = parts[parts.index("dev") + 1]
        flags = "M" if state == "PERMANENT" else ("C" if mac else "")
        rows.append((addr, "ether", mac or "--", flags, "", iface))
    lines = ["Address".ljust(25) + "HWtype".ljust(8) + "HWaddress".ljust(20)
             + "Flags Mask".ljust(22) + "Iface"]
    for addr, hwtype, mac, flags, mask, iface in rows:
        lines.append(addr.ljust(25) + hwtype.ljust(8) + mac.ljust(20)
                     + flags.ljust(6) + mask.ljust(16) + iface)
    return "\n".join(lines)


def _dhcp_iface_subnet(iface: str) -> str:
    import ipaddress
    import subprocess
    try:
        dev = subprocess.run(["uci", "-q", "get", f"network.{iface}.device"],
                             capture_output=True, text=True, timeout=5)
        device = (dev.stdout or "").strip() or iface
        out = subprocess.run(["ip", "-4", "-o", "addr", "show", "dev", device],
                             capture_output=True, text=True, timeout=5).stdout
        for token in out.split():
            if "/" in token and token[0].isdigit():
                net = ipaddress.ip_interface(token).network
                return str(net)
    except Exception:
        pass
    return ""


def _dhcp_pools(ctx: Any) -> list:
    import ipaddress
    import subprocess
    pools = []
    cfg = (ctx.store.get(["service", "dhcp-server", "shared-network-name"],
                         candidate=False) or {})
    if cfg:
        for network, body in cfg.items():
            body = body if isinstance(body, dict) else {}
            for subnet, sbody in (body.get("subnet") or {}).items():
                sbody = sbody if isinstance(sbody, dict) else {}
                static = []
                for name, m in (sbody.get("static-mapping") or {}).items():
                    if isinstance(m, dict):
                        static.append({"name": name, "ip": m.get("ip-address", ""),
                                       "mac": m.get("mac-address", "")})
                ranges = sbody.get("range") or {}
                if ranges:
                    for _rid, r in ranges.items():
                        if not isinstance(r, dict):
                            continue
                        pools.append({"network": network, "subnet": subnet,
                                      "start": r.get("start", ""),
                                      "stop": r.get("stop", ""),
                                      "static": static})
                else:
                    pools.append({"network": network, "subnet": subnet,
                                  "start": "", "stop": "", "static": static})
        return pools

    # Fallback: native OpenWrt /etc/config/dhcp (dnsmasq).
    out = subprocess.run(["uci", "show", "dhcp"], capture_output=True,
                         text=True, timeout=5).stdout
    sections = {}
    for line in out.splitlines():
        key, _, value = line.partition("=")
        parts = key.split(".")
        if len(parts) != 3:
            continue
        sections.setdefault(parts[1], {})[parts[2]] = value.strip("'\"")
    hosts = []
    for sec, opts in sections.items():
        if opts.get("ip") and opts.get("mac"):
            hosts.append({"name": opts.get("name", sec), "ip": opts["ip"],
                          "mac": opts["mac"]})
    for sec, opts in sections.items():
        start = opts.get("start")
        limit = opts.get("limit")
        if not start or opts.get("ignore") == "1":
            continue
        iface = opts.get("interface", sec)
        subnet = _dhcp_iface_subnet(iface)
        start_ip = stop_ip = ""
        if subnet:
            try:
                net = ipaddress.ip_network(subnet, strict=False)
                first = net.network_address + int(start)
                last = first + max(0, int(limit or 1) - 1)
                start_ip, stop_ip = str(first), str(last)
            except Exception:
                pass
        pools.append({"network": sec, "subnet": subnet, "start": start_ip,
                      "stop": stop_ip, "static": hosts})
    return pools


def _dhcp_leases() -> list:
    import time
    leases = []
    try:
        with open("/tmp/dhcp.leases", encoding="utf-8") as f:
            for line in f:
                parts = line.split()
                if len(parts) >= 4:
                    leases.append({
                        "expires": time.strftime(
                            "%Y-%m-%d %H:%M:%S", time.localtime(int(parts[0]))),
                        "mac": parts[1], "ip": parts[2], "host": parts[3]})
    except (OSError, ValueError):
        pass
    return leases


def _op_show_dhcp_server(ctx: Any, value: Any) -> str:
    import subprocess
    try:
        running = subprocess.run(["pidof", "dnsmasq"], capture_output=True,
                                 text=True, timeout=5).stdout.strip()
    except Exception:
        running = ""
    pools = _dhcp_pools(ctx)
    leases = _dhcp_leases()
    statics = sum(len(p["static"]) for p in pools)
    lines = [f"DHCP server:      {'running (dnsmasq)' if running else 'stopped'}",
             f"Shared networks:  {len({p['network'] for p in pools})}",
             f"Address pools:    {len(pools)}",
             f"Active leases:    {len(leases)}",
             f"Static mappings:  {statics}"]
    return "\n".join(lines)


def _op_show_dhcp_server_pools(ctx: Any, value: Any) -> str:
    import ipaddress
    pools = _dhcp_pools(ctx)
    leases = _dhcp_leases()
    if not pools:
        return "No DHCP address pools configured."
    lines = ["Shared network".ljust(18) + "Subnet".ljust(20)
             + "Range".ljust(34) + "Used".ljust(7) + "Total"]
    for pool in pools:
        used = total = 0
        if pool.get("subnet") and pool.get("start"):
            try:
                net = ipaddress.ip_network(pool["subnet"], strict=False)
                first = ipaddress.ip_address(pool["start"])
                last = ipaddress.ip_address(pool["stop"])
                total = int(last) - int(first) + 1
                for lease in leases:
                    try:
                        if ipaddress.ip_address(lease["ip"]) in net:
                            used += 1
                    except ValueError:
                        pass
            except Exception:
                pass
        rng = (f"{pool['start']}-{pool['stop']}" if pool.get("start")
               else "-")
        lines.append(pool["network"].ljust(18) + (pool.get("subnet") or "-").ljust(20)
                     + rng.ljust(34) + str(used).ljust(7) + str(total))
    return "\n".join(lines)


def _op_show_dhcp_server_leases(ctx: Any, value: Any) -> str:
    leases = _dhcp_leases()
    if not leases:
        return "No active DHCP leases."
    lines = ["Expires".ljust(21) + "MAC".ljust(20) + "IP".ljust(18)
             + "Hostname"]
    for lease in leases:
        lines.append(lease["expires"].ljust(21) + lease["mac"].ljust(20)
                     + lease["ip"].ljust(18) + lease["host"])
    return "\n".join(lines)


def _op_show_dhcp_server_static(ctx: Any, value: Any) -> str:
    pools = _dhcp_pools(ctx)
    rows = [(p["network"], s) for p in pools for s in p["static"]]
    if not rows:
        return "No static DHCP mappings configured."
    lines = ["Shared network".ljust(18) + "Name".ljust(16)
             + "IP".ljust(18) + "MAC"]
    for network, s in rows:
        lines.append(network.ljust(18) + str(s["name"]).ljust(16)
                     + str(s["ip"]).ljust(18) + str(s["mac"]))
    return "\n".join(lines)


def _proc_status(pid: str) -> dict:
    out = {}
    try:
        with open(f"/proc/{pid}/status", encoding="utf-8") as f:
            for line in f:
                key, _, value = line.partition(":")
                if key in ("Name", "Uid", "PPid"):
                    out[key] = value.strip()
    except OSError:
        pass
    return out


def _proc_tty(pid: str) -> str:
    import os
    try:
        target = os.readlink(f"/proc/{pid}/fd/0")
    except OSError:
        return ""
    if target.startswith("/dev/"):
        return target[5:]
    return ""


def _proc_start(pid: str) -> str:
    import time
    try:
        with open(f"/proc/{pid}/stat", encoding="utf-8") as f:
            fields = f.read().split()
        with open("/proc/stat", encoding="utf-8") as f:
            btime = int(f.read().split("btime ")[1].split()[0])
        return time.strftime("%Y-%m-%d %H:%M:%S",
                             time.localtime(btime + int(fields[21]) / 100.0))
    except (OSError, ValueError, IndexError):
        return "-"


def _ssh_peers() -> dict:
    """pid -> peer IP for established :22 connections."""
    import re
    import subprocess
    peers = {}
    for args in (["ss", "-tnp"], ["netstat", "-tnp"]):
        try:
            out = subprocess.run(args, capture_output=True, text=True,
                                 timeout=5).stdout
        except Exception:
            continue
        for line in out.splitlines():
            parts = line.split()
            if len(parts) < 5 or not parts[3].endswith(":22"):
                continue
            ip = parts[4].rsplit(":", 1)[0]
            m = re.search(r"pid=(\d+)", line) or re.search(r"(\d+)/", line)
            if m and ip not in ("0.0.0.0", "::", "[::]"):
                peers[m.group(1)] = ip
        if peers:
            break
    return peers


def _user_groups(user: str) -> list:
    groups = set()
    primary = ""
    try:
        with open("/etc/passwd", encoding="utf-8") as f:
            for line in f:
                parts = line.split(":")
                if parts and parts[0] == user:
                    primary = parts[3] if len(parts) > 3 else ""
                    break
    except OSError:
        pass
    try:
        with open("/etc/group", encoding="utf-8") as f:
            for line in f:
                parts = line.rstrip("\n").split(":")
                if len(parts) < 4:
                    continue
                members = parts[3].split(",")
                if user in members or (primary and parts[2] == primary):
                    groups.add(parts[0])
    except OSError:
        pass
    if not groups:
        groups.add(user)
    return sorted(groups)


def _login_ssh_sessions(peers: dict) -> list:
    """Return SSH sessions: dropbear pid, shell pid, user, ip, tty."""
    import os
    import subprocess
    shells = {"ash", "sh", "bash", "zsh", "ksh", "mksh", "login", "su"}
    sessions = []
    used_drop = set()
    try:
        pids = [d for d in os.listdir("/proc") if d.isdigit()]
    except OSError:
        pids = []
    for pid in pids:
        if _proc_status(pid).get("Name", "") not in shells:
            continue
        tty = _proc_tty(pid)
        if not tty or tty.startswith("null"):
            continue
        walk = _proc_status(pid).get("PPid", "")
        drop = ""
        for _ in range(8):
            if not walk or walk == "0":
                break
            if walk in peers:
                drop = walk
                break
            walk = _proc_status(walk).get("PPid", "")
        if not drop:
            continue
        used_drop.add(drop)
        try:
            user = (subprocess.run(["ps", "-o", "user=", "-p", pid],
                                   capture_output=True, text=True,
                                   timeout=5).stdout.strip() or "root")
        except Exception:
            user = "root"
        sessions.append({"drop": drop, "shell": pid, "user": user,
                         "ip": peers[drop], "tty": tty})
    for drop, ip in peers.items():
        if drop in used_drop:
            continue
        try:
            user = (subprocess.run(["ps", "-o", "user=", "-p", drop],
                                   capture_output=True, text=True,
                                   timeout=5).stdout.strip() or "root")
        except Exception:
            user = "root"
        sessions.append({"drop": drop, "shell": "", "user": user,
                         "ip": ip, "tty": "ssh"})
    return sessions


def _current_dropbear(peers: dict) -> str:
    import os
    pid = str(os.getpid())
    for _ in range(12):
        if pid in peers:
            return pid
        ppid = _proc_status(pid).get("PPid", "")
        if not ppid or ppid == "0":
            break
        pid = ppid
    return ""


def _disconnect_sessions(match) -> str:
    import os
    import signal
    peers = _ssh_peers()
    current = _current_dropbear(peers)
    sessions = _login_ssh_sessions(peers)
    killed = 0
    skipped = 0
    for sess in sessions:
        if not match(sess):
            continue
        if sess["drop"] == current:
            skipped += 1
            continue
        try:
            os.kill(int(sess["drop"]), signal.SIGTERM)
        except OSError:
            continue
        if sess.get("shell"):
            try:
                os.kill(int(sess["shell"]), signal.SIGTERM)
            except OSError:
                pass
        killed += 1
    if not killed:
        extra = " (current session skipped)" if skipped else ""
        return f"no matching SSH sessions{extra}"
    return f"disconnected {killed} SSH session(s)"


def _op_disconnect_user(ctx: Any, value: str) -> str:
    if not value:
        return "usage: disconnect user <username>"
    return _disconnect_sessions(lambda s: s["user"] == value)


def _op_disconnect_ssh(ctx: Any, value: str) -> str:
    if not value:
        return "usage: disconnect ssh <ip-address|tty>"
    if value.startswith("tty") or value.startswith("pts/"):
        return _disconnect_sessions(lambda s: s["tty"] == value)
    return _disconnect_sessions(lambda s: s["ip"] == value)


def _op_disconnect_tty(ctx: Any, value: str) -> str:
    if not value:
        return "usage: disconnect ssh tty <tty>"
    return _disconnect_sessions(lambda s: s["tty"] == value)


def _op_show_login(ctx: Any, value: Any) -> str:
    import getpass
    import os
    user = os.environ.get("USER") or os.environ.get("LOGNAME") or getpass.getuser()
    try:
        tty = os.ttyname(0)
        tty = tty[5:] if tty.startswith("/dev/") else tty
    except OSError:
        tty = "-"
    peers = _ssh_peers()
    ip = "-"
    pid = str(os.getpid())
    session_pid = pid
    for _ in range(12):
        status = _proc_status(pid)
        if pid in peers:
            ip = peers[pid]
            session_pid = pid
            break
        current_tty = _proc_tty(pid)
        if current_tty and not current_tty.startswith("null"):
            session_pid = pid
        ppid = status.get("PPid", "")
        if not ppid or ppid == "0":
            break
        pid = ppid
    started = _proc_start(session_pid)
    return "\n".join([
        f"login     : {user}  {tty:<10} {started} ({ip})",
        "level     : admin",
        f"user      : {user}",
        f"groups    : {' '.join(_user_groups(user))}",
    ])


def _op_show_login_user(ctx: Any, value: Any) -> str:
    import os
    import subprocess
    shells = {"ash", "sh", "bash", "zsh", "ksh", "mksh", "login", "su"}
    peers = _ssh_peers()
    users = {}
    rows = []
    seen = set()
    try:
        pids = [d for d in os.listdir("/proc") if d.isdigit()]
    except OSError:
        pids = []
    for pid in pids:
        name = _proc_status(pid).get("Name", "")
        if name not in shells:
            continue
        tty = _proc_tty(pid)
        if not tty or tty.startswith("null"):
            continue
        ppid = _proc_status(pid).get("PPid", "")
        uid = _proc_status(pid).get("Uid", "").split()[0] if _proc_status(pid).get("Uid") else ""
        user = users.get(uid)
        if user is None:
            try:
                user = (subprocess.run(["ps", "-o", "user=", "-p", pid],
                                       capture_output=True, text=True,
                                       timeout=5).stdout.strip() or "root")
            except Exception:
                user = "root"
            if uid:
                users[uid] = user
        ip = "-"
        walk = ppid
        for _ in range(8):
            if not walk or walk == "0":
                break
            if walk in peers:
                ip = peers[walk]
                break
            walk = _proc_status(walk).get("PPid", "")
        key = (user, tty, ip)
        if key in seen:
            continue
        seen.add(key)
        rows.append((user, ip, tty, _proc_start(pid)))

    # Non-interactive SSH sessions have no login shell on a pty; add them
    # from the connection table so `ssh host cmd` still shows up.
    for pid, ip in peers.items():
        if any(row[1] == ip for row in rows):
            continue
        try:
            user = (subprocess.run(["ps", "-o", "user=", "-p", pid],
                                   capture_output=True, text=True,
                                   timeout=5).stdout.strip() or "root")
        except Exception:
            user = "root"
        key = (user, "ssh", ip)
        if key in seen:
            continue
        seen.add(key)
        rows.append((user, ip, "ssh", _proc_start(pid)))

    if not rows:
        return "No users logged in."
    rows.sort(key=lambda r: (r[0], r[2]))
    lines = ["Username".ljust(12) + "IP Address".ljust(18)
             + "TTY".ljust(10) + "Login Time"]
    for user, ip, tty, started in rows:
        lines.append(user.ljust(12) + ip.ljust(18) + tty.ljust(10) + started)
    return "\n".join(lines)


def _range_text(values) -> str:
    nums = sorted({int(v) for v in values})
    if not nums:
        return "-"
    parts = []
    start = prev = nums[0]
    for n in nums[1:]:
        if n == prev + 1:
            prev = n
            continue
        parts.append(str(start) if start == prev else f"{start}-{prev}")
        start = prev = n
    parts.append(str(start) if start == prev else f"{start}-{prev}")
    return ",".join(parts)


def _parse_host_port(value: str):
    parts = (value or "").split()
    if len(parts) < 2:
        return None, None, "usage: ping {proto} <ip> <port>"
    try:
        return parts[0], int(parts[1]), ""
    except ValueError:
        return None, None, "port must be a number"


def _op_ping_tcp(ctx: Any, value: str) -> str:
    import socket
    import time
    host, port, err = _parse_host_port(value)
    if err:
        return err.replace("{proto}", "tcp")
    start = time.perf_counter()
    try:
        with socket.create_connection((host, port), timeout=2):
            pass
        elapsed = (time.perf_counter() - start) * 1000
        return f"Connected to {host}:{port}: time={elapsed:.1f} ms"
    except ConnectionRefusedError:
        return f"tcp {host}:{port}: connection refused (port closed)"
    except socket.timeout:
        return f"tcp {host}:{port}: timeout (filtered)"
    except OSError as e:  # noqa: BLE001
        return f"tcp {host}:{port}: {e}"


def _udp_payload(port: int, extra: str):
    """Return (payload, label) that should provoke a reply for known ports."""
    import os
    import struct
    if extra:
        if extra.startswith("hex:"):
            try:
                return bytes.fromhex(extra[4:]), "custom"
            except ValueError:
                return b"\x00", "custom"
        return extra.encode(), "custom"
    if port == 53:
        # DNS query: version.bind CH TXT (any response proves it is open).
        name = b"\x07version\x04bind\x00"
        question = name + struct.pack("!HH", 16, 3)
        header = struct.pack("!HHHHHH", 0x1234, 0x0100, 1, 0, 0, 0)
        return header + question, "dns"
    if port == 123:
        # NTPv3 client request.
        return b"\x1b" + b"\x00" * 47, "ntp"
    if port == 3478:
        # STUN binding request.
        return struct.pack("!HHI12s", 0x0001, 0, 0x2112A442,
                           os.urandom(12)), "stun"
    if port == 7:
        return b"vyoscli", "echo"
    return b"\x00", "generic"


def _op_ping_udp(ctx: Any, value: str) -> str:
    import socket
    import time
    parts = (value or "").split()
    if len(parts) < 2:
        return "usage: ping udp <ip> <port> [payload|hex:...]"
    host = parts[0]
    try:
        port = int(parts[1])
    except ValueError:
        return "port must be a number"
    extra = " ".join(parts[2:])
    payload, label = _udp_payload(port, extra)
    start = time.perf_counter()
    try:
        info = socket.getaddrinfo(host, port, type=socket.SOCK_DGRAM)[0]
        family, socktype, proto, _canon, addr = info
        sock = socket.socket(family, socktype, proto)
        sock.settimeout(2)
        try:
            sock.connect(addr)
            sock.send(payload)
            data = sock.recv(2048)
            elapsed = (time.perf_counter() - start) * 1000
            return (f"udp {host}:{port}: {label} reply {len(data)} byte(s), "
                    f"time={elapsed:.1f} ms")
        except (socket.timeout, ConnectionRefusedError):
            # Pure UDP has no handshake; a missing reply is inconclusive.
            # Do not derive state from ICMP errors here.
            return (f"udp {host}:{port}: no reply to {label} probe "
                    f"(open|filtered, or service does not answer)")
        finally:
            sock.close()
    except ConnectionRefusedError:
        return (f"udp {host}:{port}: no reply to {label} probe "
                f"(open|filtered, or service does not answer)")
    except OSError as e:  # noqa: BLE001
        return f"udp {host}:{port}: {e}"


def _trace_hops(target: str, iface: str = "", source: str = "",
                max_hops: int = 30) -> list:
    import re
    import subprocess
    cmd = ["traceroute", "-n", "-q", "1", "-w", "2",
           "-m", str(max_hops)]
    if iface:
        cmd += ["-i", iface]
    if source:
        cmd += ["-s", source]
    cmd.append(target)
    try:
        out = subprocess.run(cmd, capture_output=True, text=True,
                             timeout=max(20, max_hops * 2)).stdout
    except Exception as e:  # noqa: BLE001
        return [{"ttl": 0, "ip": "", "rtt": "", "error": str(e)}]
    hops = []
    for line in out.splitlines():
        m = re.match(r"^\s*(\d+)\s+(.+)$", line)
        if not m:
            continue
        ttl = int(m.group(1))
        rest = m.group(2).strip()
        if rest.startswith("*"):
            hops.append({"ttl": ttl, "ip": "", "rtt": ""})
            continue
        rtt = ""
        rm = re.search(r"([\d.]+)\s*ms", rest)
        if rm:
            rtt = rm.group(1)
        ip = rest.split()[0]
        hops.append({"ttl": ttl, "ip": ip, "rtt": rtt})
    return hops


def _ping_ok(target: str, iface: str = "") -> bool:
    import subprocess
    cmd = ["ping", "-c", "1", "-W", "1"]
    if iface:
        cmd += ["-I", iface]
    cmd.append(target)
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
    except Exception:
        return False
    text = (out.stdout or "") + (out.stderr or "")
    return "bytes from" in text or "1 packets received" in text


def _path_record(target: str, iface: str, source: str,
                 max_hops: int = 30) -> dict:
    import socket
    import time
    hops = _trace_hops(target, iface, source, max_hops)
    try:
        resolved = socket.gethostbyname(target)
    except OSError:
        resolved = target
    traced = any(h.get("ip") == resolved for h in hops)
    ping_ok = _ping_ok(target, iface)
    reached = traced or ping_ok
    last_ok = max([h["ttl"] for h in hops if h.get("ip")], default=0)
    note = ""
    if ping_ok and not traced:
        note = (f"target reachable via ICMP; traceroute stopped at TTL "
                f"{last_ok} (probe filtering)")
    elif not ping_ok:
        note = "target unreachable via ICMP"
    return {
        "time": time.strftime("%Y-%m-%d %H:%M:%S"),
        "target": target,
        "interface": iface or "-",
        "source": source or "-",
        "hops": hops,
        "reached": reached,
        "traced": traced,
        "ping_ok": ping_ok,
        "last_ok": last_ok,
        "break_at": "" if reached else (last_ok + 1),
        "note": note,
    }


def _format_path(rec: dict) -> str:
    lines = [f"Path to {rec['target']} via {rec['interface']} "
             f"({rec['time']})",
             "TTL  Hop".ljust(26) + "RTT(ms)".ljust(12) + "Status"]
    for hop in rec["hops"]:
        ip = hop.get("ip") or "*"
        rtt = hop.get("rtt") or "-"
        status = "ok" if hop.get("ip") else "no reply"
        lines.append(str(hop.get("ttl", "")).ljust(5)
                     + ip.ljust(21) + str(rtt).ljust(12) + status)
    if rec["reached"]:
        suffix = f" - {rec['note']}" if rec.get("note") else ""
        lines.append(f"Reached: yes{suffix}")
    else:
        lines.append(f"Reached: no (last responding hop {rec['last_ok']}, "
                     f"break at TTL {rec['break_at']})")
    return "\n".join(lines)


def _monitor_log_path(ctx: Any) -> str:
    directory = os.path.join(ctx.store.base_dir, "monitor")
    os.makedirs(directory, exist_ok=True)
    return os.path.join(directory, "path.jsonl")


def _op_monitor_path(ctx: Any, value: str) -> str:
    import json
    import time
    parts = (value or "").split()
    if not parts:
        return ("usage: monitor path <target> [interface <if>] "
                "[source <ip>] [count N] [interval S] [max-hops N]")
    target = parts[0]
    opts = {}
    i = 1
    while i < len(parts):
        key = parts[i]
        if i + 1 < len(parts):
            opts[key] = parts[i + 1]
            i += 2
        else:
            i += 1
    count = int(opts.get("count", 1))
    interval = int(opts.get("interval", 10))
    max_hops = int(opts.get("max-hops", 30))
    iface = opts.get("interface", "")
    source = opts.get("source", "")
    path = _monitor_log_path(ctx)
    outputs = []
    for round_no in range(1, count + 1):
        rec = _path_record(target, iface, source, max_hops)
        outputs.append(f"=== round {round_no}/{count} ===")
        outputs.append(_format_path(rec))
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        if round_no < count:
            time.sleep(interval)
    outputs.append(f"history: {path}")
    return "\n".join(outputs)


def _op_show_monitor_path(ctx: Any, value: str) -> str:
    import json
    path = os.path.join(ctx.store.base_dir, "monitor", "path.jsonl")
    try:
        with open(path, encoding="utf-8") as f:
            records = [json.loads(line) for line in f if line.strip()]
    except (OSError, ValueError):
        return "No path history."
    if value:
        records = [r for r in records if r.get("target") == value]
    if not records:
        return "No path history."
    latest = {}
    for rec in records:
        key = (rec.get("target"), rec.get("interface"))
        latest[key] = rec
    lines = ["Target".ljust(18) + "Interface".ljust(12)
             + "Last seen".ljust(21) + "Hops".ljust(6)
             + "Reached".ljust(9) + "Break"]
    for (_target, iface), rec in sorted(latest.items()):
        lines.append(str(rec.get("target")).ljust(18)
                     + str(iface).ljust(12)
                     + str(rec.get("time")).ljust(21)
                     + str(len(rec.get("hops", []))).ljust(6)
                     + ("yes" if rec.get("reached") else "no").ljust(9)
                     + str(rec.get("break_at", "")))
    return "\n".join(lines)


def _op_show_system_cpu(ctx: Any, value: Any) -> str:
    vendor = model = ""
    procs = []
    sockets = set()
    cores = 0
    siblings = 0
    mhz = ""
    try:
        with open("/proc/cpuinfo", encoding="utf-8") as f:
            blocks = f.read().split("\n\n")
        for block in blocks:
            fields = {}
            for line in block.splitlines():
                key, _, val = line.partition(":")
                if key.strip():
                    fields[key.strip()] = val.strip()
            if not fields:
                continue
            if "processor" in fields:
                procs.append(fields["processor"])
            vendor = vendor or fields.get("vendor_id", "")
            model = model or fields.get("model name", "")
            if "physical id" in fields:
                sockets.add(fields["physical id"])
            try:
                cores = max(cores, int(fields.get("cpu cores", 0)))
                siblings = max(siblings, int(fields.get("siblings", 0)))
            except ValueError:
                pass
            if not mhz and fields.get("cpu MHz"):
                mhz = fields["cpu MHz"]
    except OSError:
        pass
    threads = int(siblings / cores) if cores and siblings else 1
    return "\n".join([
        f"CPU Vendor:       {vendor or 'unknown'}",
        f"Model:            {model or 'unknown'}",
        f"Total CPUs:       {_range_text(procs)}",
        f"Sockets:          {len(sockets) or 1}",
        f"Cores:            {cores or len(procs)}",
        f"Threads:          {threads}",
        f"Current MHz:      {mhz or 'unknown'}",
    ])


def _image_info() -> str:
    info = {}
    try:
        with open("/etc/openwrt_release", encoding="utf-8") as f:
            for line in f:
                key, _, val = line.partition("=")
                if key.strip():
                    info[key.strip()] = val.strip().strip("'\"")
    except OSError:
        pass
    name = f"{info.get('DISTRIB_ID', 'OpenWrt')} {info.get('DISTRIB_RELEASE', '')}".strip()
    desc = info.get("DISTRIB_DESCRIPTION", name)
    return desc or name


def _op_show_system_image(ctx: Any, value: Any) -> str:
    try:
        with open("/proc/sys/kernel/osrelease", encoding="utf-8") as f:
            kernel = f.read().strip()
    except OSError:
        kernel = "unknown"
    return "\n".join([
        "The system currently has the following image(s) installed:",
        "",
        f"   1: {_image_info()} (running image)",
        "",
        f"Kernel: {kernel}",
    ])


def _op_show_system_image_storage(ctx: Any, value: Any) -> str:
    import subprocess
    try:
        return subprocess.run(["df", "-h", "/"], capture_output=True,
                              text=True, timeout=5).stdout.strip()
    except Exception as e:  # noqa: BLE001
        return f"df failed: {e}"


def _op_show_system_image_version(ctx: Any, value: Any) -> str:
    return _image_info()


def _op_show_system_login_users(ctx: Any, value: Any) -> str:
    import os
    import subprocess
    sessions = _login_ssh_sessions(_ssh_peers())
    shadow = {}
    try:
        with open("/etc/shadow", encoding="utf-8") as f:
            for line in f:
                parts = line.rstrip("\n").split(":")
                if len(parts) >= 2:
                    shadow[parts[0]] = parts[1]
    except OSError:
        pass
    rows = []
    try:
        with open("/etc/passwd", encoding="utf-8") as f:
            for line in f:
                parts = line.rstrip("\n").split(":")
                if len(parts) < 7:
                    continue
                name, shell = parts[0], parts[6]
                if "nologin" in shell or "false" in shell or shell == "/bin/sync":
                    continue
                locked = shadow.get(name, "").startswith(("!", "*")) if shadow else False
                tty = frm = last = "-"
                for sess in sessions:
                    if sess.get("user") == name:
                        tty = sess.get("tty", "-")
                        frm = sess.get("ip", "-")
                        last = _proc_start(str(sess.get("drop", "")))
                        break
                rows.append((name, "linux", str(locked), tty, frm, last))
    except OSError:
        pass
    if not rows:
        return "No user accounts."
    lines = ["Username".ljust(14) + "Type".ljust(8) + "Locked".ljust(10)
             + "Tty".ljust(9) + "From".ljust(18) + "Last login"]
    for user, typ, locked, tty, frm, last in rows:
        lines.append(user.ljust(14) + typ.ljust(8) + locked.ljust(10)
                     + tty.ljust(9) + frm.ljust(18) + last)
    return "\n".join(lines)


def _op_show_system_connections(ctx: Any, value: str = "") -> str:
    import subprocess
    proto = (value or "").lower()
    args = ["netstat", "-tnap"] if proto == "tcp" else (
        ["netstat", "-unap"] if proto == "udp" else ["netstat", "-tunap"])
    try:
        out = subprocess.run(args, capture_output=True, text=True,
                             timeout=5).stdout
    except Exception as e:  # noqa: BLE001
        return f"netstat failed: {e}"
    lines = []
    for line in out.splitlines():
        parts = line.split()
        if not parts:
            continue
        if parts[0] == "Proto":
            lines.append("Proto".ljust(7) + "Recv-Q".rjust(7) + "Send-Q".rjust(7)
                         + " " + "Local Address".ljust(23)
                         + "Foreign Address".ljust(23) + "State")
            continue
        if parts[0] not in ("tcp", "tcp6", "udp", "udp6"):
            continue
        if len(parts) > 5 and ("/" in parts[-1] or parts[-1] == "-"):
            parts = parts[:-1]
        if parts[0].startswith("udp") and len(parts) >= 5:
            state = " ".join(parts[5:]) if len(parts) > 5 else ""
            lines.append(parts[0].ljust(7) + parts[1].rjust(7)
                         + parts[2].rjust(7) + " " + parts[3].ljust(23)
                         + parts[4].ljust(23) + state)
        elif len(parts) >= 6:
            lines.append(parts[0].ljust(7) + parts[1].rjust(7)
                         + parts[2].rjust(7) + " " + parts[3].ljust(23)
                         + parts[4].ljust(23) + " ".join(parts[5:]))
    return "\n".join(lines) or "No connections."


def _op_show_policy_local_route(ctx: Any, value: Any) -> str:
    rules = (ctx.store.get(["policy", "local-route", "rule"],
                           candidate=False) or {})
    if not rules:
        return "No local-route rules configured."
    lines = ["Rule".ljust(8) + "Source".ljust(24) + "Table"]
    for num, rule in sorted(rules.items(), key=lambda kv: str(kv[0])):
        if not isinstance(rule, dict):
            continue
        source = rule.get("source", "")
        table = (rule.get("set") or {}).get("table", "")
        lines.append(str(num).ljust(8) + str(source).ljust(24) + str(table))
    return "\n".join(lines)


def _op_show_bgp_summary(ctx: Any, value: Any) -> str:
    return _vtysh_show("show bgp ipv4 unicast summary")


def _bgp_neighbor_ips() -> list:
    import re
    out = _vtysh_show("show bgp ipv4 unicast summary")
    ips = []
    for line in out.splitlines():
        m = re.match(r"^(\d{1,3}(?:\.\d{1,3}){3})\s", line)
        if m:
            ips.append(m.group(1))
    return ips


def _op_show_bgp_neighbors(ctx: Any, value: Any) -> str:
    if not value:
        return _vtysh_show("show bgp ipv4 unicast summary")
    return _vtysh_show(f"show bgp neighbor {value}")


def _op_show_bgp_neighbor_received_routes(ctx: Any, value: Any) -> str:
    if not value:
        return "Usage: show ip bgp neighbors <ip> received-routes"
    return _vtysh_show(
        f"show bgp ipv4 unicast neighbors {value} received-routes")


def _op_show_bgp(ctx: Any, value: Any) -> str:
    return _vtysh_show("show bgp ipv4 unicast")


def _op_show_ip_route_static(ctx: Any, value: Any) -> str:
    import shutil
    import subprocess
    if shutil.which("vtysh"):
        try:
            r = subprocess.run(["vtysh", "-c", "show ip route static"],
                               capture_output=True, text=True, timeout=20)
            out = (r.stdout or "").strip()
            if out and "failed to connect" not in out and "Exiting:" not in out:
                return out
            if not out:
                return _ROUTE_CODES
        except Exception:
            pass
    return _ip_route_fallback("static")


def _op_show_ip_route_connected(ctx: Any, value: Any) -> str:
    return _vtysh_route("show ip route connected",
                        lambda: _ip_route_fallback("connected"))


def _op_show_ip_route_bgp(ctx: Any, value: Any) -> str:
    return _vtysh_route("show ip route bgp",
                        lambda: _ip_route_fallback("bgp"))


def _op_show_ip_route_summary(ctx: Any, value: Any) -> str:
    return _vtysh_route("show ip route summary",
                        lambda: _ip_route_fallback("all"))
