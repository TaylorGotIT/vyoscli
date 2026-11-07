"""op 模式命令函数 - show 类"""
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


def _op_show_bgp_summary(ctx: Any, value: Any) -> str:
    return _vtysh_show("show bgp ipv4 unicast summary")


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
