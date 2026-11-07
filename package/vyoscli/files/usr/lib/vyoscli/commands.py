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



from . import config_tree
from . import schema
from .op_show import (
    _op_show_dependencies,
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
    _op_show_bgp,
    _op_show_dhcp_server,
    _op_show_dhcp_server_leases,
    _op_show_dhcp_server_pools,
    _op_show_dhcp_server_static,
    _op_show_policy_local_route,
    _bgp_neighbor_ips,
    _op_show_bgp_neighbors,
    _op_show_bgp_neighbor_received_routes,
    _op_show_arp,
    _op_show_bgp_summary,
    _op_show_ip_route_static,
    _op_show_ip_route_connected,
    _op_show_ip_route_summary,
    _op_show_ip_route_bgp,
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
def _container_runtime() -> str:
    import shutil
    for name in ("podman", "docker", "nerdctl"):
        if shutil.which(name):
            return name
    return ""


def _op_show_container_image(ctx: Any, value: Any) -> str:
    runtime = _container_runtime()
    if not runtime:
        return ("no container runtime installed "
                "(podman/docker/nerdctl)")
    try:
        out = subprocess.run([runtime, "images"],
                             capture_output=True, text=True, timeout=15)
        text = (out.stdout or "").strip()
        return text or (out.stderr or "").strip() or "(no images)"
    except Exception as e:  # noqa: BLE001
        return f"{runtime} images failed: {e}"


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


def _list_ethernet_ifaces() -> list:
    import subprocess
    try:
        r = subprocess.run(["ls", "/sys/class/net/"], capture_output=True, text=True, timeout=5)
        return [n for n in r.stdout.split() if n.startswith("eth") or n.startswith("en")]
    except Exception:
        return []


def _op_show_drift(ctx: Any, value: Any) -> str:
    changed = ctx.store.drift()
    if changed is None:
        return "No applied manifest yet (commit once to start tracking)."
    if not changed:
        return "No drift: committed UCI sections still match the running config."
    lines = [f"  {state:<8} {section}" for section, state in changed]
    return ("UCI sections changed since the last commit "
            "(edit by hand, restore, or upgrade):\n" + "\n".join(lines))


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
    tree.op("show dependencies", help="Check required packages", action=_op_show_dependencies)
    tree.op("show interfaces", help="Show interface summary",
            action=_op_show_interfaces)
    # show interface ethernet <ifname>
    from .op_show import _op_show_interface_detail
    show_if = tree.op_root.children["show"].children["interfaces"]
    eth_node = Node(name="ethernet", help="Ethernet interface name",
                    value_type="string", action=_op_show_interface_detail)
    eth_node._completion = _list_ethernet_ifaces  # type: ignore[attr-defined]
    show_if.add(eth_node)
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
    show_sys.add(Node(name="drift",
                      help="UCI sections changed since the last commit",
                      action=_op_show_drift))
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
    show_route.add(Node(name="bgp", help="Show BGP routes",
                        action=_op_show_ip_route_bgp))
    show_route.action = _op_show_ip_route
    show_ip.add(show_route)
    show_bgp = Node(name="bgp", help="BGP information")
    show_bgp.add(Node(name="summary", help="Show BGP summary",
                      action=_op_show_bgp_summary))
    show_bgp.add(Node(name="table", help="Show BGP table",
                      action=_op_show_bgp))
    show_bgp.action = _op_show_bgp
    neighbors = Node(name="neighbors", help="BGP neighbors")
    tpl = Node(name="", help="Show detailed BGP IPv4 unicast neighbor information",
               value_type="string", action=_op_show_bgp_neighbors)
    tpl.dynamic = _bgp_neighbor_ips
    tpl.add(Node(name="received-routes",
                 help="Show routes received from this neighbor",
                 action=_op_show_bgp_neighbor_received_routes))
    neighbors.add(tpl)
    neighbors.action = _op_show_bgp_neighbors
    show_bgp.add(neighbors)
    show_ip.add(show_bgp)
    tree.op_root.children["show"].add(show_ip)
    tree.op("show arp", help="Show ARP table", action=_op_show_arp)
    tree.op("show policy local-route", help="Show local-route policy",
            action=_op_show_policy_local_route)

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
    tree.op("show dhcp server", help="Show DHCP server status",
            action=_op_show_dhcp_server)
    tree.op("show dhcp server leases", help="Show active DHCP leases",
            action=_op_show_dhcp_server_leases)
    tree.op("show dhcp server pools", help="Show DHCP address pool usage",
            action=_op_show_dhcp_server_pools)
    tree.op("show dhcp server static", help="Show static DHCP mappings",
            action=_op_show_dhcp_server_static)
    tree.op("show smartdns", help="Show smartdns status",
            action=_op_show_smartdns)
    tree.op("show hardware usb", help="List USB devices",
            action=_op_show_hardware_usb)

    # ---------- configuration mode: set / delete / edit ----------
    # The whole config tree is generated from config_tree.py (NodeSpec),
    # which in turn is produced from schema definitions.
    for verb in ("set", "delete", "edit"):
        root = Node(name=verb, help=f"{verb} configuration node")
        tree.cfg_root.add(root)
        schema.build_tree(root, config_tree.TREE, _cfg_noop, store=store)

    # config-mode top-level verbs
    for verb, help_text in (
        ("commit", "Commit candidate (add 'confirmed [min]' for auto-rollback; 'commit confirm' to cancel)"),
        ("sync", "Re-apply running config to the backend (drift repair)"),
        ("discard", "Discard uncommitted changes"),
        ("save", "Save running config to boot"),
        ("rollback", "Roll back to a prior snapshot (optional: <timestamp>)"),
        ("show", "Show candidate or running config"),
        ("up", "Move up one level"),
        ("next", "Move into sub-configuration (alias: edit)"),
        ("exit", "Exit current level or config mode"),
    ):
        tree.cfg_root.add(Node(name=verb, help=help_text))

    # Help/completion only: these are dispatched by cli._run_cfg, but the tree
    # needs the children so `show ?` and Tab can list them.
    show_node = tree.cfg_root.children.get("show")
    if show_node is not None:
        show_node.add(Node(name="configuration",
                           help="Show candidate (or running) configuration"))
        show_node.add(Node(name="system", help="Show the running configuration"))
        show_node.add(Node(name="history", help="List commit snapshots"))

    return tree
