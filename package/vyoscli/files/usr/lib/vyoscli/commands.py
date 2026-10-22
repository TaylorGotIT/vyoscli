"""Built-in command definitions.

Operational mode mirrors VyOS:
  show version | interface | configuration [commands|json] |
  system uptime|memory|storage|processes|kernel-messages|login
  ping <host> | configure | exit
"""

from __future__ import annotations

import os
import platform
import json
import subprocess
from typing import Any, List


def _run(cmd: List[str]) -> str:
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        return out.stdout or out.stderr or f"(no output: {' '.join(cmd)})"
    except FileNotFoundError:
        return f"(command not found: {cmd[0]})"
    except Exception as e:  # noqa: BLE001
        return f"{cmd[0]} failed: {e}"



from .op_show import (
    _op_show_log,
    _op_show_history,
    _op_show_version,
    _op_show_configuration,
    _op_show_configuration_commands,
    _op_show_configuration_json,
    _op_show_interfaces,
    _op_show_system_summary,
    _op_show_system_uptime,
    _op_show_system_memory,
    _op_show_system_storage,
    _op_show_system_processes,
    _op_show_system_kmsg,
    _op_show_system_login,
    _op_show_ip_route,
    _op_show_ip_route_static,
    _op_show_ip_route_connected,
    _op_show_ip_route_summary,
)

# ---------- ping ----------
def _op_ping(ctx: Any, value: str) -> str:
    if not value:
        return "ping: host required"
    try:
        out = subprocess.run(["ping", "-c", "4", "-W", "2", value],
                             capture_output=True, text=True, timeout=15)
        return out.stdout or out.stderr or "(no output)"
    except FileNotFoundError:
        try:
            out = subprocess.run(["ping", "-n", "4", value],
                                 capture_output=True, text=True, timeout=15)
            return out.stdout
        except Exception as e:  # noqa: BLE001
            return f"ping failed: {e}"


# ---------- container images (operational) ----------
def _op_show_container_image(ctx: Any, value: Any) -> str:
    try:
        out = subprocess.run(["podman", "images"],
                             capture_output=True, text=True, timeout=15)
        return out.stdout or out.stderr or "(no images)"
    except FileNotFoundError:
        return "podman not installed (use 'set container ... commit' to auto-install)"
    except Exception as e:  # noqa: BLE001
        return f"podman images failed: {e}"


def _op_add_container_image(ctx: Any, value: str) -> str:
    if not value:
        return "usage: add container image <image:tag>"
    try:
        out = subprocess.run(["podman", "pull", value],
                             capture_output=True, text=True, timeout=600)
        return out.stdout + out.stderr
    except FileNotFoundError:
        return "podman not installed (use 'set container ... commit' to auto-install)"
    except Exception as e:  # noqa: BLE001
        return f"podman pull failed: {e}"


def _op_delete_container_image(ctx: Any, value: str) -> str:
    if not value:
        return "usage: delete container image <image:tag>"
    try:
        out = subprocess.run(["podman", "rmi", value],
                             capture_output=True, text=True, timeout=30)
        return out.stdout + out.stderr
    except FileNotFoundError:
        return "podman not installed"
    except Exception as e:  # noqa: BLE001
        return f"podman rmi failed: {e}"


def _op_show_container(ctx: Any, value: Any) -> str:
    try:
        out = subprocess.run(["podman", "ps"],
                             capture_output=True, text=True, timeout=15)
        return out.stdout or out.stderr or "(no running containers)"
    except FileNotFoundError:
        return "podman not installed"
    except Exception as e:  # noqa: BLE001
        return f"podman ps failed: {e}"


def _op_show_dhcp_lease(ctx: Any, value: Any) -> str:
    try:
        with open("/tmp/dhcp.leases", encoding="utf-8") as f:
            return f.read() or "(no leases)"
    except FileNotFoundError:
        return "(no dhcp leases file - dnsmasq not active?)"
    except Exception as e:  # noqa: BLE001
        return f"dhcp leases failed: {e}"


def _op_service_action(action: str):
    def _act(ctx: Any, svc: str) -> str:
        import subprocess
        script = f"/etc/init.d/{svc}"
        try:
            r = subprocess.run([script, action], capture_output=True, text=True, timeout=30)
            if r.returncode == 0:
                return f"{svc}: {action} OK"
            return f"{svc}: {action} failed: {r.stderr.strip()}"
        except FileNotFoundError:
            return f"Unknown service: {svc} (no {script})"
        except Exception as e:  # noqa: BLE001
            return f"{svc}: {action} error: {e}"
    return _act


def _op_list_services(prefix: str):
    import os
    try:
        return [f for f in os.listdir("/etc/init.d")
                if os.access(f"/etc/init.d/{f}", os.X_OK)]
    except Exception:
        return []


def _op_show_hardware_usb(ctx: Any, value: Any) -> str:
    import subprocess
    r = subprocess.run(["lsusb"], capture_output=True, text=True, timeout=5)
    return r.stdout or "No USB devices"


def _op_show_smartdns(ctx: Any, value: Any) -> str:
    try:
        out = subprocess.run(["/etc/init.d/smartdns", "status"],
                             capture_output=True, text=True, timeout=10)
        return out.stdout or out.stderr or "(smartdns not running)"
    except Exception:
        try:
            out = subprocess.run(["ss", "-lunp"], capture_output=True, text=True, timeout=5)
            return out.stdout
        except Exception as e:  # noqa: BLE001
            return f"smartdns status failed: {e}"


def _cfg_noop(ctx: Any, value: Any) -> str:
    return ""


def build_tree(store: Any) -> CommandTree:
    from .tree import CommandTree, Node
    tree = CommandTree()

    # ---------- operational mode ----------
    tree.op("configure", help="Enter configuration mode",
            action=lambda c, v: c.enter_configure())
    tree.op("exit", help="Exit the CLI", action=lambda c, v: c.quit())
    tree.op("quit", help="Exit the CLI", action=lambda c, v: c.quit())

    # show version / interface
    tree.op("show version", help="Show system version", action=_op_show_version)
    tree.op("show interface", help="Show interface summary",
            action=_op_show_interfaces)
    tree.op("show history", help="Show command history", action=_op_show_history)
    tree.op("show log", help="Show system log (logread)", action=_op_show_log)

    # show configuration [commands|json]
    show_cfg = Node(name="configuration", help="Show running configuration",
                    action=_op_show_configuration)
    show_cfg.add(Node(name="commands",
                      help="Show running config as set commands",
                      action=_op_show_configuration_commands))
    show_cfg.add(Node(name="json",
                      help="Show running config in JSON format",
                      action=_op_show_configuration_json))
    tree.op_root.children["show"].add(show_cfg)

    # show system <sub>
    show_sys = Node(name="system", help="System status",
                    action=_op_show_system_summary)
    show_sys.add(Node(name="uptime", help="Show how long the system has been up",
                      action=_op_show_system_uptime))
    show_sys.add(Node(name="memory", help="Show system memory usage",
                      action=_op_show_system_memory))
    show_sys.add(Node(name="storage", help="Show filesystem usage",
                      action=_op_show_system_storage))
    show_sys.add(Node(name="processes", help="Show running processes",
                      action=_op_show_system_processes))
    show_sys.add(Node(name="kernel-messages",
                      help="Show kernel ring buffer (last 30 lines)",
                      action=_op_show_system_kmsg))
    show_sys.add(Node(name="login", help="Show local user accounts",
                      action=_op_show_system_login))
    tree.op_root.children["show"].add(show_sys)

    tree.op("ping", help="Ping a host", value_type="host", action=_op_ping)

    # show ip route [static|connected|summary]
    show_ip = Node(name="ip", help="IP information")
    show_route = Node(name="route", help="IP routing table")
    show_route.add(Node(name="static", help="Show static routes",
                        action=_op_show_ip_route_static))
    show_route.add(Node(name="connected", help="Show connected routes",
                        action=_op_show_ip_route_connected))
    show_route.add(Node(name="summary", help="Route table summary",
                        action=_op_show_ip_route_summary))
    show_route.action = _op_show_ip_route
    show_ip.add(show_route)
    tree.op_root.children["show"].add(show_ip)

    # show container image
    tree.op("show container image", help="List podman images",
            action=_op_show_container_image)

    # add / delete container image <img>
    tree.op("add container image", help="Pull a container image (podman pull)",
            value_type="str", action=_op_add_container_image)
    tree.op("delete container image", help="Remove a container image (podman rmi)",
            value_type="str", action=_op_delete_container_image)

    # restart / reload / stop service <name>
    for verb, help_txt in [
        ("restart", "(Re)start a system service"),
        ("reload", "Reload a system service"),
    ]:
        tree.op(f"{verb} service", help=f"{help_txt} (e.g. ssh/firewall/dnsmasq)",
                value_type="str", action=_op_service_action(verb))

    # show container / dhcp lease / smartdns
    tree.op("show container", help="List running podman containers",
            action=_op_show_container)
    tree.op("show dhcp lease", help="Show DHCP leases",
            action=_op_show_dhcp_lease)
    tree.op("show smartdns", help="Show smartdns status",
            action=_op_show_smartdns)
    tree.op("show hardware usb", help="List USB devices",
            action=_op_show_hardware_usb)

    # ---------- configuration mode: set / delete / edit ----------
    for verb in ("set", "delete", "edit"):
        root = Node(name=verb, help=f"{verb} configuration node")
        tree.cfg_root.add(root)

        sys_named = Node(name="system", help="System parameters")
        root.add(sys_named)
        sys_named.add(Node(name="host-name", help="System hostname",
                           value_type="host", action=_cfg_noop))
        sys_named.add(Node(name="name-server", help="Upstream DNS for dnsmasq (client queries)",
                           value_type="ipv4", action=_cfg_noop))
        sys_named.add(Node(name="dns", help="System resolver for router itself (/etc/resolv.conf)",
                           value_type="ipv4", action=_cfg_noop))
        sys_named.add(Node(name="timezone", help="IANA timezone (e.g. Asia/Shanghai)",
                           value_type="str", action=_cfg_noop))
        sys_named.add(Node(name="domain-search", help="Domain search suffix (repeatable)",
                     value_type="str", action=_cfg_noop))
        sys_named.add(Node(name="ntp", help="NTP server hostname (repeatable)",
                           value_type="str", action=_cfg_noop))
        sys_named.add(Node(name="language", help="System locale (e.g. zh_cn, en)",
                           value_type="str", action=_cfg_noop))
        hw = Node(name="hardware", help="Manual hardware inventory")
        sys_named.add(hw)
        hw.add(Node(name="vendor", help="Hardware vendor name",
                    value_type="str", action=_cfg_noop))
        hw.add(Node(name="model", help="Hardware model",
                    value_type="str", action=_cfg_noop))
        hw.add(Node(name="serial", help="Hardware serial number (S/N)",
                    value_type="str", action=_cfg_noop))

        if_root = Node(name="interfaces", help="Interface parameters")
        root.add(if_root)
        eth = Node(name="ethernet", help="Ethernet interfaces")
        if_root.add(eth)

        template = Node(name="*", help="Per-interface config")
        template.add(Node(name="address", help="IPv4 address/prefix",
                          value_type="ipv4net", action=_cfg_noop))
        template.add(Node(name="description", help="Interface description",
                          value_type="str", action=_cfg_noop))
        eth.dynamic = lambda: ["lo", "eth0", "eth1", "eth2", "wlan0"]
        eth._dyn_template = template  # type: ignore[attr-defined]

        # interfaces wireless wlan0 ...
        wl = Node(name="wireless", help="Wi-Fi access points")
        if_root.add(wl)
        wl_tpl = Node(name="*", help="Per-radio AP config")
        wl_tpl.add(Node(name="mode", help="AP mode (default ap)",
                        value_type="str", action=_cfg_noop))
        wl_tpl.add(Node(name="ssid", help="SSID broadcast name",
                        value_type="str", action=_cfg_noop))
        wl_tpl.add(Node(name="channel", help="Channel (e.g. 6, 36, 149)",
                        value_type="str", action=_cfg_noop))
        wl_tpl.add(Node(name="hw-mode", help="11g (2.4G) or 11a (5G)",
                        value_type="str", action=_cfg_noop))
        wl_tpl.add(Node(name="security", help="wpa2 | wpa3 | none",
                        value_type="str", action=_cfg_noop))
        wl_tpl.add(Node(name="passphrase", help="Wi-Fi password (8+ chars)",
                        value_type="str", action=_cfg_noop))
        wl_tpl.add(Node(name="network", help="Bridge to a logical network (default lan)",
                        value_type="str", action=_cfg_noop))
        def _existing_wl(store=store):
            try:
                return list((store.candidate.get("interfaces", {})
                             .get("wireless", {}) or {}).keys())
            except Exception:
                return []
        wl.dynamic = _existing_wl
        wl._dyn_template = wl_tpl  # type: ignore[attr-defined]

        # interface role: lan / wan (bind a logical role to a physical NIC)
        for role_name in ("lan", "wan"):
            rn = Node(name=role_name, help=f"Bind {role_name} logical interface to a NIC")
            if_root.add(rn)
            rn.add(Node(name="device", help=f"Physical NIC for {role_name} (e.g. eth0)",
                        value_type="str", action=_cfg_noop))

        # interface bridge br0 port ethX
        br = Node(name="bridge", help="Bridge device")
        if_root.add(br)
        br_tpl = Node(name="*", help="Per-bridge")
        br_tpl.add(Node(name="port", help="Add a port (repeatable)",
                        value_type="str", action=_cfg_noop))
        br_tpl.add(Node(name="mac", help="Bridge MAC address (for rebinding)",
                        value_type="str", action=_cfg_noop))
        br_tpl.add(Node(name="mac-rebinding", help="Enable transparent bridge (bump-in-the-wire)",
                        value_type="bool", action=_cfg_noop))
        br_tpl.add(Node(name="vlan-aware", help="Enable VLAN filtering",
                        value_type="bool", action=_cfg_noop))
        # vlan sub-tree
        vlan = Node(name="vlan", help="VLAN membership", action=_cfg_noop)
        br_tpl.add(vlan)
        vlan_tpl = Node(name="*", help="VLAN ID")
        vlan_tpl.add(Node(name="untagged", help="Untagged port (repeatable)", value_type="str", action=_cfg_noop))
        vlan_tpl.add(Node(name="tagged", help="Tagged port (repeatable)", value_type="str", action=_cfg_noop))
        vlan.dynamic = lambda: []
        vlan._dyn_template = vlan_tpl
        def _existing_br(store=store):
            try:
                return list((store.candidate.get("interfaces", {}).get("bridge", {}) or {}).keys())
            except Exception:
                return []
        br.dynamic = _existing_br
        br._dyn_template = br_tpl  # type: ignore[attr-defined]

        # interface dummy dum0 address x.x.x.x/32
        dm = Node(name="dummy", help="Dummy loopback-like interface")
        if_root.add(dm)
        dm_tpl = Node(name="*", help="Per-dummy")
        dm_tpl.add(Node(name="address", help="Static address/prefix",
                        value_type="ipv4net", action=_cfg_noop))
        def _existing_dm(store=store):
            try:
                return list((store.candidate.get("interfaces", {}).get("dummy", {}) or {}).keys())
            except Exception:
                return []
        dm.dynamic = _existing_dm
        dm._dyn_template = dm_tpl  # type: ignore[attr-defined]

        # interfaces wireguard wg0 ...
        wg = Node(name="wireguard", help="WireGuard VPN interface")
        if_root.add(wg)
        wg_tpl = Node(name="*", help="Per-wg iface")
        wg_tpl.add(Node(name="address", help="VPN address/prefix (repeatable)",
                        value_type="ipv4net", action=_cfg_noop))
        wg_tpl.add(Node(name="private-key", help="WireGuard private key",
                        value_type="str", action=_cfg_noop))
        wg_tpl.add(Node(name="listen-port", help="Listen UDP port",
                        value_type="port", action=_cfg_noop))
        peer = Node(name="peer", help="Remote peer public key")
        wg_tpl.add(peer)
        peer_tpl = Node(name="*", help="Per-peer")
        peer_tpl.add(Node(name="endpoint", help="Endpoint host[:port]",
                          value_type="str", action=_cfg_noop))
        peer_tpl.add(Node(name="allowed-ips", help="Allowed IPs, e.g. 10.0.0.2/32",
                          value_type="str", action=_cfg_noop))
        peer.dynamic = lambda: []
        peer._dyn_template = peer_tpl  # type: ignore[attr-defined]
        def _existing_wg(store=store):
            try:
                return list((store.candidate.get("interfaces", {}).get("wireguard", {}) or {}).keys())
            except Exception:
                return []
        wg.dynamic = _existing_wg
        wg._dyn_template = wg_tpl  # type: ignore[attr-defined]

        # interfaces openvpn vtun0 ...
        ov = Node(name="openvpn", help="OpenVPN tunnel")
        if_root.add(ov)
        ov_tpl = Node(name="*", help="Per-tunnel")
        ov_tpl.add(Node(name="mode", help="server|client", value_type="str", action=_cfg_noop))
        ov_tpl.add(Node(name="proto", help="udp|tcp", value_type="str", action=_cfg_noop))
        ov_tpl.add(Node(name="port", help="Listen port", value_type="port", action=_cfg_noop))
        ov_tpl.add(Node(name="dev", help="tun|tap", value_type="str", action=_cfg_noop))
        ov_tpl.add(Node(name="ca", help="CA cert path", value_type="str", action=_cfg_noop))
        ov_tpl.add(Node(name="cert", help="Server cert path", value_type="str", action=_cfg_noop))
        ov_tpl.add(Node(name="key", help="Server key path", value_type="str", action=_cfg_noop))
        ov_tpl.add(Node(name="dh", help="DH pem path", value_type="str", action=_cfg_noop))
        ov_tpl.add(Node(name="server", help="VPN pool: x.x.x.x 255.255.255.0",
                        value_type="str", action=_cfg_noop))
        ov_tpl.add(Node(name="push", help="Push option to client (repeatable)",
                        value_type="str", action=_cfg_noop))
        def _existing_ov(store=store):
            try:
                return list((store.candidate.get("interfaces", {}).get("openvpn", {}) or {}).keys())
            except Exception:
                return []
        ov.dynamic = _existing_ov
        ov._dyn_template = ov_tpl  # type: ignore[attr-defined]

        # interfaces tunnel tun0 ...
        tn = Node(name="tunnel", help="GRE/IPIP tunnel")
        if_root.add(tn)
        tn_tpl = Node(name="*", help="Per-tunnel")
        tn_tpl.add(Node(name="encapsulation", help="gre | ipip", value_type="str", action=_cfg_noop))
        tn_tpl.add(Node(name="local-ip", help="Local outer IPv4", value_type="ipv4", action=_cfg_noop))
        tn_tpl.add(Node(name="remote-ip", help="Remote outer IPv4", value_type="ipv4", action=_cfg_noop))
        tn_tpl.add(Node(name="address", help="Inner tunnel IPv4/prefix",
                        value_type="ipv4net", action=_cfg_noop))
        def _existing_tn(store=store):
            try:
                return list((store.candidate.get("interfaces", {}).get("tunnel", {}) or {}).keys())
            except Exception:
                return []
        tn.dynamic = _existing_tn
        tn._dyn_template = tn_tpl  # type: ignore[attr-defined]

        # interfaces vxlan vxlan0 ...
        vx = Node(name="vxlan", help="VXLAN tunnel")
        if_root.add(vx)
        vx_tpl = Node(name="*", help="Per-vxlan")
        vx_tpl.add(Node(name="vni", help="VXLAN Network Identifier (1-16777215)",
                        value_type="str", action=_cfg_noop))
        vx_tpl.add(Node(name="local-ip", help="Local outer IPv4", value_type="ipv4", action=_cfg_noop))
        vx_tpl.add(Node(name="remote-ip", help="Remote outer IPv4", value_type="ipv4", action=_cfg_noop))
        vx_tpl.add(Node(name="address", help="Inner tunnel IPv4/prefix",
                        value_type="ipv4net", action=_cfg_noop))
        def _existing_vx(store=store):
            try:
                return list((store.candidate.get("interfaces", {}).get("vxlan", {}) or {}).keys())
            except Exception:
                return []
        vx.dynamic = _existing_vx
        vx._dyn_template = vx_tpl  # type: ignore[attr-defined]

        # protocols static route <prefix> [next-hop <ip> | interface <if>]
        proto = Node(name="protocols", help="Routing protocols")
        root.add(proto)
        static = Node(name="static", help="Static routing")
        proto.add(static)
        route = Node(name="route",
                     help="Static IPv4 route (e.g. 10.0.0.0/8)")
        static.add(route)
        route_tpl = Node(name="*", help="Per-route options")
        route_tpl.add(Node(name="next-hop",
                           help="Next-hop gateway IPv4",
                           value_type="ipv4", action=_cfg_noop))
        route_tpl.add(Node(name="interface",
                           help="Egress interface",
                           value_type="str", action=_cfg_noop))
        route_tpl.add(Node(name="blackhole",
                           help="Silently drop packets",
                           value_type="bool", action=_cfg_noop))
        route_tpl.add(Node(name="reject",
                           help="Send ICMP unreachable",
                           value_type="bool", action=_cfg_noop))
        # Tab-completion: list prefixes already in the candidate config
        def _existing_routes(store=store):
            try:
                return list((store.candidate.get("protocols", {})
                             .get("static", {}).get("route", {}) or {}).keys())
            except Exception:
                return []
        route.dynamic = _existing_routes
        route._dyn_template = route_tpl  # type: ignore[attr-defined]

        # protocols bgp ...
        bgp = Node(name="bgp", help="BGP routing (FRR)")
        proto.add(bgp)
        bgp.add(Node(name="local-as", help="Local AS number",
                     value_type="int", action=_cfg_noop))
        bgp.add(Node(name="router-id", help="BGP router-id",
                     value_type="ipv4", action=_cfg_noop))
        nb = Node(name="neighbor", help="BGP neighbor")
        bgp.add(nb)
        nb_dyn = Node(name="", help="Neighbor IP", dynamic=True, action=_cfg_noop)
        nb.add(nb_dyn)
        nb_dyn.add(Node(name="remote-as", help="Peer AS number",
                        value_type="int", action=_cfg_noop))
        nb_dyn.add(Node(name="description", help="Neighbor description",
                        value_type="str", action=_cfg_noop))
        nb_dyn.add(Node(name="route-map-in", help="Inbound route-map name",
                        value_type="str", action=_cfg_noop))
        nb_dyn.add(Node(name="route-map-out", help="Outbound route-map name",
                        value_type="str", action=_cfg_noop))
        bgp.add(Node(name="network", help="Advertise prefix (repeatable)",
                     value_type="ipv4_cidr", action=_cfg_noop))

        # protocols route-map ...
        rm = Node(name="route-map", help="Route-map policy")
        proto.add(rm)
        rm_name = Node(name="", help="Route-map name", dynamic=True, action=_cfg_noop)
        rm.add(rm_name)
        rm_action = Node(name="permit", help="Permit rule", action=_cfg_noop)
        rm_name.add(rm_action)
        rm_rule = Node(name="", help="Rule number", dynamic=True, action=_cfg_noop)
        rm_action.add(rm_rule)
        rm_set = Node(name="set", help="Set attribute")
        rm_rule.add(rm_set)
        rm_set.add(Node(name="local-preference", help="BGP local-preference",
                        value_type="int", action=_cfg_noop))
        rm_set.add(Node(name="med", help="BGP MED",
                        value_type="int", action=_cfg_noop))
        rm_set.add(Node(name="community", help="BGP community (e.g. 65001:100)",
                        value_type="str", action=_cfg_noop))
        rm_set.add(Node(name="next-hop", help="Set next-hop",
                        value_type="ipv4", action=_cfg_noop))
        # match
        rm_match = Node(name="match", help="Match condition")
        rm_rule.add(rm_match)
        rm_match_com = Node(name="community", help="Match community-list")
        rm_match.add(rm_match_com)
        rm_match_com.add(Node(name="community-list", help="Community-list number",
                              value_type="str", action=_cfg_noop))

        # policy community-list
        pol = Node(name="policy", help="Routing policy")
        root.add(pol)
        comlist = Node(name="community-list", help="BGP community-list")
        pol.add(comlist)
        cl_num = Node(name="", help="List number", dynamic=True, action=_cfg_noop)
        comlist.add(cl_num)
        cl_rule = Node(name="rule", help="Rule number", dynamic=True, action=_cfg_noop)
        cl_num.add(cl_rule)
        cl_rule.add(Node(name="action", help="permit/deny", value_type="str", action=_cfg_noop))
        cl_rule.add(Node(name="description", help="Description", value_type="str", action=_cfg_noop))
        cl_rule.add(Node(name="regex", help="Community regex", value_type="str", action=_cfg_noop))

        # bgp peer-group
        bgp_pg = Node(name="peer-group", help="BGP peer group")
        proto_bgp = None
        for n in root.children.values():
            if n.name == "protocols":
                for c in n.children.values():
                    if c.name == "bgp":
                        proto_bgp = c
                        break
        if proto_bgp:
            pg_dyn = Node(name="", help="Peer-group name", dynamic=True, action=_cfg_noop)
            proto_bgp.add(bgp_pg)
            bgp_pg.add(pg_dyn)
            pg_dyn.add(Node(name="remote-as", help="Remote AS", value_type="int", action=_cfg_noop))
            pg_dyn.add(Node(name="update-source", help="Update source IP", value_type="ipv4", action=_cfg_noop))
            pg_dyn.add(Node(name="route-map-import", help="Inbound route-map", value_type="str", action=_cfg_noop))
            pg_dyn.add(Node(name="soft-reconfiguration", help="Soft reconfig inbound", value_type="str", action=_cfg_noop))

        # service smartdns ...
        svc = Node(name="service", help="System services")
        root.add(svc)
        sdns = Node(name="smartdns", help="SmartDNS forwarding resolver")
        svc.add(sdns)
        sdns.add(Node(name="enabled", help="Enable SmartDNS",
                      value_type="boolean", action=_cfg_noop))
        sdns.add(Node(name="port", help="Listen port (default 5333)",
                      value_type="port", action=_cfg_noop))
        sdns.add(Node(name="speed-check-mode",
                      help="Probe mode: e.g. 'ping,tcp:80'",
                      value_type="str", action=_cfg_noop))
        sdns.add(Node(name="forbid-aaaa",
                      help="Suppress IPv6 (AAAA) answers",
                      value_type="boolean", action=_cfg_noop))
        sdns.add(Node(name="listen-address", help="Bind IP (default 0.0.0.0)",
                      value_type="ipv4", action=_cfg_noop))
        sdns.add(Node(name="disable", help="Disable smartdns",
                      value_type="bool", action=_cfg_noop))

        server = Node(name="server", help="Upstream DNS server")
        sdns.add(server)
        srv_tpl = Node(name="*", help="Per-server options")
        srv_tpl.add(Node(name="ip", help="Server IP", value_type="ipv4",
                         action=_cfg_noop))
        srv_tpl.add(Node(name="port", help="Server port", value_type="port",
                         action=_cfg_noop))
        srv_tpl.add(Node(name="type", help="udp|tcp|tls|https",
                         value_type="str", action=_cfg_noop))
        def _existing_servers(store=store):
            try:
                return list((store.candidate.get("service", {})
                             .get("smartdns", {}).get("server", {}) or {}).keys())
            except Exception:
                return []
        server.dynamic = _existing_servers
        server._dyn_template = srv_tpl  # type: ignore[attr-defined]

        dset = Node(name="domain-set", help="Named domain list")
        sdns.add(dset)
        dset_tpl = Node(name="*", help="Per-domain-set options")
        dset_tpl.add(Node(name="domain", help="Add a domain to the set",
                          value_type="str", action=_cfg_noop))
        dset_tpl.add(Node(name="file",
                          help="Domain list file (recommended: /etc/vyoscli/lists/<name>.txt)",
                          value_type="str", action=_cfg_noop))
        def _existing_sets(store=store):
            try:
                return list((store.candidate.get("service", {})
                             .get("smartdns", {}).get("domain-set", {}) or {}).keys())
            except Exception:
                return []
        dset.dynamic = _existing_sets
        dset._dyn_template = dset_tpl  # type: ignore[attr-defined]

        drule = Node(name="domain-rule", help="Route a domain-set to upstream(s)")
        sdns.add(drule)
        dr_tpl = Node(name="*", help="Per-rule options")
        dr_tpl.add(Node(name="domain-set", help="Which domain-set to match",
                        value_type="str", action=_cfg_noop))
        dr_tpl.add(Node(name="forward", help="Upstream server name (repeatable)",
                        value_type="str", action=_cfg_noop))
        def _existing_rules(store=store):
            try:
                return list((store.candidate.get("service", {})
                             .get("smartdns", {}).get("domain-rule", {}) or {}).keys())
            except Exception:
                return []
        drule.dynamic = _existing_rules
        drule._dyn_template = dr_tpl  # type: ignore[attr-defined]

        addr = Node(name="address", help="Intranet static address mapping")
        sdns.add(addr)
        addr_tpl = Node(name="*", help="Per-domain mapping")
        addr_tpl.add(Node(name="ip", help="Answer IP", value_type="ipv4",
                          action=_cfg_noop))
        def _existing_addrs(store=store):
            try:
                return list((store.candidate.get("service", {})
                             .get("smartdns", {}).get("address", {}) or {}).keys())
            except Exception:
                return []
        addr.dynamic = _existing_addrs
        addr._dyn_template = addr_tpl  # type: ignore[attr-defined]

        # traffic-policy shaper ...
        tp = Node(name="traffic-policy", help="QoS traffic shaping")
        root.add(tp)
        shaper = Node(name="shaper", help="Per-IP bandwidth limiter")
        tp.add(shaper)
        sh_dyn = Node(name="", help="Policy name", dynamic=True, action=_cfg_noop)
        shaper.add(sh_dyn)
        sh_dyn.add(Node(name="interface", help="Egress interface", value_type="str", action=_cfg_noop))
        sh_dyn.add(Node(name="bandwidth", help="Total bandwidth (e.g. 100mbit)", value_type="str", action=_cfg_noop))
        sh_dyn.add(Node(name="per-ip", help="Per-IP bandwidth limit (e.g. 10mbit)", value_type="str", action=_cfg_noop))

        # service sqm ...
        sqm = Node(name="sqm", help="SQM smart queue management")
        svc.add(sqm)
        sqm.add(Node(name="interface", help="WAN interface", value_type="str", action=_cfg_noop))
        sqm.add(Node(name="download", help="Download bandwidth kbps", value_type="int", action=_cfg_noop))
        sqm.add(Node(name="upload", help="Upload bandwidth kbps", value_type="int", action=_cfg_noop))
        sqm.add(Node(name="qdisc", help="cake / fq_codel", value_type="str", action=_cfg_noop))

        # service kcp ...
        acc = Node(name="kcp", help="KCP tunnel (kcptun)")
        svc.add(acc)
        acc_tpl = Node(name="*", help="Tunnel name")
        acc_tpl.add(Node(name="mode", help="c/client or s/server", value_type="str", action=_cfg_noop))
        acc_tpl.add(Node(name="kcp-mode", help="fast2/fast3/normal", value_type="str", action=_cfg_noop))
        acc_tpl.add(Node(name="local-ip", help="Local listen IP", value_type="ipv4", action=_cfg_noop))
        acc_tpl.add(Node(name="local-port", help="Local listen port", value_type="port", action=_cfg_noop))
        acc_tpl.add(Node(name="remote-ip", help="Remote IP", value_type="ipv4", action=_cfg_noop))
        acc_tpl.add(Node(name="remote-port", help="Remote port", value_type="port", action=_cfg_noop))
        acc.dynamic = lambda: []
        acc._dyn_template = acc_tpl

        # service tcp-accelerate ...
        tcp_acc = Node(name="tcp-accelerate", help="TCP congestion control")
        svc.add(tcp_acc)
        tcp_acc.add(Node(name="congestion-control", help="bbr/cubic/hybla",
                         value_type="str", action=_cfg_noop))
        tcp_acc.add(Node(name="fq-codel", help="Enable fq_codel qdisc",
                         value_type="bool", action=_cfg_noop))

        # system login user ...
        login = Node(name="login", help="Login user management")
        sys_named.add(login)
        login_user = Node(name="user", help="Local user")
        login.add(login_user)
        user_dyn = Node(name="", help="Username", dynamic=True, action=_cfg_noop)
        login_user.add(user_dyn)
        user_dyn.add(Node(name="full-name", help="Full name", value_type="str", action=_cfg_noop))
        user_dyn.add(Node(name="disable", help="Disable account", value_type="bool", action=_cfg_noop))
        auth = Node(name="authentication", help="Authentication")
        user_dyn.add(auth)
        auth.add(Node(name="plaintext-password", help="Plain password", value_type="str", action=_cfg_noop))
        auth.add(Node(name="encrypted-password", help="Encrypted password", value_type="str", action=_cfg_noop))
        pk = Node(name="public-keys", help="SSH public keys")
        auth.add(pk)
        pk_dyn = Node(name="", help="Key identifier", dynamic=True, action=_cfg_noop)
        pk.add(pk_dyn)
        pk_dyn.add(Node(name="key", help="Public key content", value_type="str", action=_cfg_noop))
        pk_dyn.add(Node(name="type", help="ssh-rsa/ssh-ed25519", value_type="str", action=_cfg_noop))

        # policy route-redirect ...
        pol = Node(name="policy", help="Policy")
        root.add(pol)
        rr = Node(name="route-redirect", help="Transparent proxy redirect")
        pol.add(rr)
        rr_dyn = Node(name="", help="Policy name", dynamic=True, action=_cfg_noop)
        rr.add(rr_dyn)
        rr_rule = Node(name="rule", help="Rule")
        rr_dyn.add(rr_rule)
        rr_rule_dyn = Node(name="", help="Rule number", dynamic=True, action=_cfg_noop)
        rr_rule.add(rr_rule_dyn)
        rr_rule_dyn.add(Node(name="dport", help="Destination port to match", value_type="port", action=_cfg_noop))
        rr_rule_dyn.add(Node(name="redirect-to", help="Redirect to IP:port", value_type="str", action=_cfg_noop))

        # vrf name ...
        vrf = Node(name="vrf", help="Virtual Routing and Forwarding")
        root.add(vrf)
        vrf_name = Node(name="name", help="VRF instance")
        vrf.add(vrf_name)
        vrf_dyn = Node(name="", help="VRF name", dynamic=True, action=_cfg_noop)
        vrf_name.add(vrf_dyn)
        vrf_dyn.add(Node(name="table", help="Routing table ID", value_type="int", action=_cfg_noop))

        # vpn ipsec ...
        vpn = Node(name="vpn", help="VPN")
        root.add(vpn)
        ipsec = Node(name="ipsec", help="IPsec VPN")
        vpn.add(ipsec)
        # ike-group
        ike = Node(name="ike-group", help="IKE Phase 1 group")
        ipsec.add(ike)
        ike_dyn = Node(name="", help="IKE group name", dynamic=True, action=_cfg_noop)
        ike.add(ike_dyn)
        ike_dyn.add(Node(name="lifetime", help="IKE lifetime seconds", value_type="int", action=_cfg_noop))
        ike_prop = Node(name="proposal", help="IKE proposal")
        ike_dyn.add(ike_prop)
        ike_prop_dyn = Node(name="", help="Proposal number", dynamic=True, action=_cfg_noop)
        ike_prop.add(ike_prop_dyn)
        ike_prop_dyn.add(Node(name="encryption", help="aes256/aes128", value_type="str", action=_cfg_noop))
        ike_prop_dyn.add(Node(name="hash", help="sha256/sha1", value_type="str", action=_cfg_noop))
        ike_prop_dyn.add(Node(name="dh-group", help="DH group (14/19/20)", value_type="int", action=_cfg_noop))
        # esp-group
        esp = Node(name="esp-group", help="ESP Phase 2 group")
        ipsec.add(esp)
        esp_dyn = Node(name="", help="ESP group name", dynamic=True, action=_cfg_noop)
        esp.add(esp_dyn)
        esp_dyn.add(Node(name="lifetime", help="ESP lifetime seconds", value_type="int", action=_cfg_noop))
        esp_prop = Node(name="proposal", help="ESP proposal")
        esp_dyn.add(esp_prop)
        esp_prop_dyn = Node(name="", help="Proposal number", dynamic=True, action=_cfg_noop)
        esp_prop.add(esp_prop_dyn)
        esp_prop_dyn.add(Node(name="encryption", help="aes256/aes128", value_type="str", action=_cfg_noop))
        esp_prop_dyn.add(Node(name="hash", help="sha256/sha1", value_type="str", action=_cfg_noop))
        # peer
        peer = Node(name="site-to-site", help="Site-to-Site VPN")
        ipsec.add(peer)
        peer_root = Node(name="peer", help="Remote peer IP")
        peer.add(peer_root)
        peer_dyn = Node(name="", help="Peer IP", dynamic=True, action=_cfg_noop)
        peer_root.add(peer_dyn)
        peer_dyn.add(Node(name="local-address", help="Local public IP", value_type="ipv4", action=_cfg_noop))
        peer_dyn.add(Node(name="remote-address", help="Remote public IP", value_type="ipv4", action=_cfg_noop))
        peer_dyn.add(Node(name="local-id", help="Local ID", value_type="str", action=_cfg_noop))
        peer_dyn.add(Node(name="remote-id", help="Remote ID", value_type="str", action=_cfg_noop))
        peer_dyn.add(Node(name="secret", help="PSK secret", value_type="str", action=_cfg_noop))
        peer_dyn.add(Node(name="ike-group", help="IKE group name", value_type="str", action=_cfg_noop))
        peer_dyn.add(Node(name="esp-group", help="ESP group name", value_type="str", action=_cfg_noop))
        tun = Node(name="tunnel", help="Tunnel")
        peer_dyn.add(tun)
        tun_dyn = Node(name="", help="Tunnel number", dynamic=True, action=_cfg_noop)
        tun.add(tun_dyn)
        tun_dyn.add(Node(name="local-prefix", help="Local subnet", value_type="ipv4_cidr", action=_cfg_noop))
        tun_dyn.add(Node(name="remote-prefix", help="Remote subnet", value_type="ipv4_cidr", action=_cfg_noop))

        # vpn ipsec remote-access
        ra = Node(name="remote-access", help="Remote access IPsec (roadwarrior)")
        ipsec.add(ra)
        ra.add(Node(name="enabled", help="Enable remote access", value_type="bool", action=_cfg_noop))
        ra.add(Node(name="local-id", help="Server ID", value_type="str", action=_cfg_noop))
        ra.add(Node(name="secret", help="PSK secret", value_type="str", action=_cfg_noop))
        ra.add(Node(name="pool-start", help="Client pool start IP", value_type="ipv4", action=_cfg_noop))
        ra.add(Node(name="pool-end", help="Client pool end IP", value_type="ipv4", action=_cfg_noop))
        ra.add(Node(name="dns", help="DNS server for clients", value_type="ipv4", action=_cfg_noop))

        # service console-server ...
        cs = Node(name="console-server", help="Serial console server (ser2net)")
        svc.add(cs)
        cs_dyn = Node(name="", help="Serial device (e.g. ttyUSB0)", dynamic=True, action=_cfg_noop)
        cs.add(cs_dyn)
        cs_dyn.add(Node(name="speed", help="Baud rate (e.g. 9600, 115200)",
                         value_type="int", action=_cfg_noop))
        cs_dyn.add(Node(name="ssh-port", help="TCP port for remote console access",
                         value_type="port", action=_cfg_noop))
        cs_dyn.add(Node(name="description", help="Device description",
                         value_type="str", action=_cfg_noop))
        cs_dyn.add(Node(name="alias", help="Short alias for connect console",
                         value_type="str", action=_cfg_noop))
        cs_dyn.add(Node(name="data-bits", help="Data bits (7 or 8, default 8)",
                         value_type="int", action=_cfg_noop))
        cs_dyn.add(Node(name="parity", help="Parity (even|odd|none, default none)",
                         value_type="str", action=_cfg_noop))
        cs_dyn.add(Node(name="stop-bits", help="Stop bits (1 or 2, default 1)",
                         value_type="int", action=_cfg_noop))

        # service crontab <name> schedule/command/description
        cron = Node(name="crontab", help="Scheduled jobs (writes /etc/crontabs/root)")
        svc.add(cron)
        cron_tpl = Node(name="*", help="Per-job options")
        cron_tpl.add(Node(name="schedule",
                          help="Cron schedule: 'm h dom mon dow'",
                          value_type="str", action=_cfg_noop))
        cron_tpl.add(Node(name="script",
                          help="Script path (recommended: /etc/vyoscli/scripts/<name>.sh)",
                          value_type="str", action=_cfg_noop))
        cron_tpl.add(Node(name="description",
                          help="Free-text description",
                          value_type="str", action=_cfg_noop))
        def _existing_cron(store=store):
            try:
                return list((store.candidate.get("service", {})
                             .get("crontab", {}) or {}).keys())
            except Exception:
                return []
        cron.dynamic = _existing_cron
        cron._dyn_template = cron_tpl  # type: ignore[attr-defined]

        # service dhcp-server shared-network-name <name> ...
        dhcp = Node(name="dhcp-server", help="DHCP server")
        svc.add(dhcp)
        dhcp_shared = Node(name="shared-network-name", help="Shared network name", action=_cfg_noop)
        dhcp.add(dhcp_shared)
        dhcp_tpl = Node(name="*", help="Per-subnet DHCP")
        dhcp_tpl.add(Node(name="subnet", help="Subnet CIDR (e.g. 192.168.1.0/24)",
                          value_type="ipv4net", action=_cfg_noop))
        dhcp_tpl.add(Node(name="interface", help="Interface name", value_type="str", action=_cfg_noop))
        dhcp_tpl.add(Node(name="gateway", help="Default gateway", value_type="ipv4", action=_cfg_noop))
        dhcp_tpl.add(Node(name="dns", help="DNS server (repeatable)", value_type="ipv4", action=_cfg_noop))
        dhcp_tpl.add(Node(name="domain", help="Domain name", value_type="str", action=_cfg_noop))
        dhcp_tpl.add(Node(name="domain-search", help="Domain search suffix", value_type="str", action=_cfg_noop))
        dhcp_tpl.add(Node(name="wpad-url", help="WPAD URL (option 252)", value_type="str", action=_cfg_noop))
        # range
        range_node = Node(name="range", help="DHCP range", action=_cfg_noop)
        dhcp_tpl.add(range_node)
        range_tpl = Node(name="*", help="Range index")
        range_tpl.add(Node(name="start", help="Range start IP", value_type="ipv4", action=_cfg_noop))
        range_tpl.add(Node(name="stop", help="Range end IP", value_type="ipv4", action=_cfg_noop))
        range_node.dynamic = lambda: []
        range_node._dyn_template = range_tpl
        # static mapping
        static = Node(name="static-mapping", help="Static MAC-IP binding", action=_cfg_noop)
        dhcp_tpl.add(static)
        static_tpl = Node(name="*", help="Mapping name")
        static_tpl.add(Node(name="ip-address", help="Fixed IP", value_type="ipv4", action=_cfg_noop))
        static_tpl.add(Node(name="mac-address", help="MAC address", value_type="str", action=_cfg_noop))
        static.dynamic = lambda: []
        static._dyn_template = static_tpl
        def _existing_dhcp_shared(store=store):
            try:
                return list((store.candidate.get("service", {})
                             .get("dhcp-server", {})
                             .get("shared-network-name", {}) or {}).keys())
            except Exception:
                return []
        dhcp_shared.dynamic = _existing_dhcp_shared
        dhcp_shared._dyn_template = dhcp_tpl  # type: ignore[attr-defined]

        # service ssh ... (dropbear)
        ssh = Node(name="ssh", help="SSH access (dropbear)")
        svc.add(ssh)
        ssh.add(Node(name="port", help="Listen port (default 22)",
                     value_type="port", action=_cfg_noop))
        ssh.add(Node(name="listen-address", help="Bind address (default 0.0.0.0)",
                     value_type="ipv4", action=_cfg_noop))
        ssh.add(Node(name="password-auth", help="Allow password login (true/false)",
                     value_type="bool", action=_cfg_noop))
        ssh.add(Node(name="root-login", help="Allow root SSH login (true/false)",
                     value_type="bool", action=_cfg_noop))
        ssh.add(Node(name="disable", help="Disable SSH server",
                     value_type="bool", action=_cfg_noop))

        # service adguard ...
        ag = Node(name="adguard", help="AdGuardHome DNS-adblock (containerized)")
        svc.add(ag)
        ag.add(Node(name="enabled", help="Enable AdGuardHome",
                    value_type="bool", action=_cfg_noop))
        ag.add(Node(name="port", help="DNS listen port (default 53)",
                    value_type="port", action=_cfg_noop))
        ag.add(Node(name="web-port", help="Web UI port (default 3000)",
                    value_type="port", action=_cfg_noop))
        ag.add(Node(name="listen-address", help="Bind IP (default 0.0.0.0)",
                    value_type="ipv4", action=_cfg_noop))
        ag.add(Node(name="disable", help="Disable AdGuardHome",
                    value_type="bool", action=_cfg_noop))

        # service dnsmasq ...
        dm = Node(name="dnsmasq", help="dnsmasq resolver")
        svc.add(dm)
        dm.add(Node(name="port", help="DNS listen port (default 53)",
                    value_type="port", action=_cfg_noop))
        dm.add(Node(name="listen-address", help="Bind IP (default 0.0.0.0)",
                    value_type="ipv4", action=_cfg_noop))
        dm.add(Node(name="disable", help="Disable dnsmasq",
                    value_type="bool", action=_cfg_noop))
        ag.add(Node(name="upstream", help="Upstream DNS (repeatable, configured in web UI)",
                    value_type="str", action=_cfg_noop))

        # firewall zone / forwarding / rule
        fw = Node(name="firewall", help="Firewall policy")
        root.add(fw)
        # zone <name>
        zone = Node(name="zone", help="Firewall zone")
        fw.add(zone)
        zone_tpl = Node(name="*", help="Per-zone")
        zone_tpl.add(Node(name="network", help="UCI network name bound to zone",
                          value_type="str", action=_cfg_noop))
        for d in ("input", "output", "forward"):
            zone_tpl.add(Node(name=d, help=f"Default {d} policy: ACCEPT/DROP/REJECT",
                              value_type="str", action=_cfg_noop))
        zone.dynamic = lambda: []
        zone._dyn_template = zone_tpl  # type: ignore[attr-defined]
        # forwarding <name> src <zone> dest <zone>
        fwd = Node(name="forwarding", help="Inter-zone forwarding")
        fw.add(fwd)
        fwd_tpl = Node(name="*", help="Per-forwarding")
        fwd_tpl.add(Node(name="src", help="Source zone", value_type="str", action=_cfg_noop))
        fwd_tpl.add(Node(name="dest", help="Destination zone", value_type="str", action=_cfg_noop))
        fwd.dynamic = lambda: []
        fwd._dyn_template = fwd_tpl  # type: ignore[attr-defined]
        # rule <num> ...
        rule = Node(name="rule", help="Firewall rule (by order number)")
        fw.add(rule)
        rule_tpl = Node(name="*", help="Per-rule")
        rule_tpl.add(Node(name="name", help="Rule name", value_type="str", action=_cfg_noop))
        rule_tpl.add(Node(name="src", help="Source zone (default *)", value_type="str", action=_cfg_noop))
        rule_tpl.add(Node(name="dest-port", help="Destination port", value_type="port", action=_cfg_noop))
        rule_tpl.add(Node(name="target", help="ACCEPT/DROP/REJECT", value_type="str", action=_cfg_noop))
        rule.dynamic = lambda: []
        rule._dyn_template = rule_tpl  # type: ignore[attr-defined]

        # nat ...
        nat = Node(name="nat", help="Network Address Translation")
        root.add(nat)
        sn = Node(name="source", help="Source NAT")
        nat.add(sn)
        sn_rule = Node(name="rule", help="Source NAT rule")
        sn.add(sn_rule)
        sn_tpl = Node(name="*", help="Per-rule")
        sn_tpl.add(Node(name="out-interface", help="Outgoing interface (e.g. wan)",
                        value_type="str", action=_cfg_noop))
        sn_tpl.add(Node(name="translation", help="Translation type (masquerade)",
                        value_type="str", action=_cfg_noop))
        sn_rule._dyn_template = sn_tpl
        sn_rule.dynamic = lambda: []
        dn = Node(name="destination", help="Destination NAT / port forward")
        nat.add(dn)
        dn_rule = Node(name="rule", help="Destination NAT rule")
        dn.add(dn_rule)
        dn_tpl = Node(name="*", help="Per-rule")
        dn_tpl.add(Node(name="in-interface", help="Incoming interface (e.g. wan)",
                        value_type="str", action=_cfg_noop))
        dn_tpl.add(Node(name="port", help="External port",
                        value_type="port", action=_cfg_noop))
        dn_tpl.add(Node(name="to", help="Internal IP to forward to",
                        value_type="ipv4", action=_cfg_noop))
        dn_rule._dyn_template = dn_tpl
        dn_rule.dynamic = lambda: []

        # container <name> ... (podman)
        ctr = Node(name="container", help="Podman containers")
        root.add(ctr)
        ctr_tpl = Node(name="*", help="Per-container options")
        ctr_tpl.add(Node(name="image", help="Container image (e.g. nginx:alpine)",
                         value_type="str", action=_cfg_noop))
        ctr_tpl.add(Node(name="network", help="podman network name",
                         value_type="str", action=_cfg_noop))
        ctr_tpl.add(Node(name="port", help="Port mapping host:container (repeatable)",
                         value_type="str", action=_cfg_noop))
        ctr_tpl.add(Node(name="volume", help="Bind mount host:container (repeatable)",
                         value_type="str", action=_cfg_noop))
        ctr_tpl.add(Node(name="restart", help="Restart policy: always|on-failure|no",
                         value_type="str", action=_cfg_noop))
        ctr_tpl.add(Node(name="command", help="Override container command",
                         value_type="str", action=_cfg_noop))
        env_node = Node(name="environment", help="Environment variables")
        ctr_tpl.add(env_node)
        env_tpl = Node(name="*", help="Per-env-var")
        env_tpl.add(Node(name="value", help="Variable value",
                         value_type="str", action=_cfg_noop))
        env_node._dyn_template = env_tpl  # type: ignore[attr-defined]
        env_node.dynamic = lambda: []
        def _existing_containers(store=store):
            try:
                return list((store.candidate.get("container", {}) or {}).keys())
            except Exception:
                return []
        ctr.dynamic = _existing_containers
        ctr._dyn_template = ctr_tpl  # type: ignore[attr-defined]

    # config-mode top-level verbs
    for verb, help_text in (
        ("commit", "Commit candidate (add 'confirmed [min]' for auto-rollback; 'commit confirm' to cancel)"),
        ("discard", "Discard uncommitted changes"),
        ("save", "Save running config to boot"),
        ("rollback", "Roll back to a prior snapshot (optional: <timestamp>)"),
        ("show", "Show candidate or running config"),
        ("up", "Move up one level"),
        ("next", "Move into sub-configuration (alias: edit)"),
        ("exit", "Exit current level or config mode"),
    ):
        tree.cfg_root.add(Node(name=verb, help=help_text))

    return tree
