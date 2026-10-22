"""op 模式命令函数 - show 类"""
from typing import Any


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
        f"Hardware vendor:   {hw.get('vendor', '-')}\n"
        f"Hardware model:    {hw.get('model', '-')}\n"
        f"Hardware serial:   {hw.get('serial', '-')}\n"
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
    eth_cfg = ctx.store.get(["interfaces", "ethernet"], candidate=False) or {}
    br_cfg = ctx.store.get(["interfaces", "bridge"], candidate=False) or {}
    desc_map = {}
    for cfg in (eth_cfg, br_cfg):
        for name, c in cfg.items():
            if isinstance(c, dict) and c.get("description"):
                desc_map[name] = c["description"]

    # get link info (mac, mtu, state)
    try:
        r = subprocess.run(["ip", "-o", "link"], capture_output=True, text=True, timeout=5)
        link_out = r.stdout
    except Exception:
        link_out = ""

    # parse link info
    link_map = {}
    for line in link_out.splitlines():
        parts = line.split()
        if len(parts) < 4:
            continue
        iface = parts[1].rstrip(":")
        state = "u" if "UP" in line else "D"
        # get mac (ether)
        mac = "--"
        for i, p in enumerate(parts):
            if p == "link/ether":
                mac = parts[i + 1]
                break
        # get mtu
        mtu = "1500"
        for i, p in enumerate(parts):
            if p == "mtu":
                mtu = parts[i + 1]
                break
        link_map[iface] = (mac, mtu, state)

    # get addr info
    try:
        r = subprocess.run(["ip", "-o", "addr"], capture_output=True, text=True, timeout=5)
        addr_out = r.stdout
    except Exception:
        addr_out = ""

    # parse addr info
    addr_map = {}
    for line in addr_out.splitlines():
        parts = line.split()
        if len(parts) < 4:
            continue
        iface = parts[1]
        for i, p in enumerate(parts):
            if p in ("inet", "inet6"):
                if iface not in addr_map:
                    addr_map[iface] = []
                addr_map[iface].append(parts[i + 1])
                break

    # build rows
    rows = []
    for iface in link_map:
        mac, mtu, state = link_map[iface]
        addrs = addr_map.get(iface, [])
        addr = addrs[0] if addrs else "--"
        rows.append((iface, addr, mac, mtu, state, desc_map.get(iface, "")))

    # sort: lo first, then eth, then others
    rows.sort(key=lambda x: (0 if x[0] == "lo" else (1 if x[0].startswith("eth") else 2), x[0]))

    # column widths
    name_w = max(len(r[0]) for r in rows) if rows else 10
    name_w = max(name_w, 10)
    addr_w = max(len(r[1]) for r in rows) if rows else 15
    addr_w = max(addr_w, 18)
    mac_w = 17
    mtu_w = 6

    lines = [
        "Codes: S - State, L - Link, u - Up, D - Down, A - Admin Down",
        "Interface".ljust(name_w + 2) +
        "IP Address".ljust(addr_w + 2) +
        "MAC".ljust(mac_w + 2) +
        "MTU".ljust(mtu_w + 2) +
        "S/L    Description",
        "-" * (name_w + addr_w + mac_w + mtu_w + 30),
    ]
    for iface, addr, mac, mtu, state, desc in rows:
        lines.append(
            iface.ljust(name_w + 2) +
            addr.ljust(addr_w + 2) +
            mac.ljust(mac_w + 2) +
            mtu.ljust(mtu_w + 2) +
            f"{state}/{state}   ".ljust(6) +
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
        # add stats
        try:
            s = subprocess.run(["ip", "-s", "link", "show", value], capture_output=True, text=True, timeout=5)
            out += "\n\n" + s.stdout.strip()
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


def _op_show_ip_route(ctx: Any, value: Any) -> str:
    import subprocess
    try:
        r = subprocess.run(["ip", "route"], capture_output=True, text=True)
        return r.stdout.strip()
    except Exception:
        return "n/a"


def _op_show_ip_route_static(ctx: Any, value: Any) -> str:
    import subprocess
    try:
        r = subprocess.run(["ip", "route", "show", "proto", "static"], capture_output=True, text=True)
        return r.stdout.strip()
    except Exception:
        return "n/a"


def _op_show_ip_route_connected(ctx: Any, value: Any) -> str:
    import subprocess
    try:
        r = subprocess.run(["ip", "route", "show", "proto", "kernel"], capture_output=True, text=True)
        return r.stdout.strip()
    except Exception:
        return "n/a"


def _op_show_ip_route_summary(ctx: Any, value: Any) -> str:
    import subprocess
    try:
        r = subprocess.run(["ip", "route"], capture_output=True, text=True)
        lines = r.stdout.strip().splitlines()
        return f"Total routes: {len(lines)}"
    except Exception:
        return "n/a"
