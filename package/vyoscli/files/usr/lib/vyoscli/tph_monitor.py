#!/usr/bin/env python3
"""Transparent bridge hijack monitor (service tph).

Watches /run/tph.json, identifies the WAN port from the gateway MAC in the
bridge FDB, syncs the bridge MAC and installs the nftables shield/hijack rules.
"""
import json
import logging
import subprocess
import time
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
Log = logging.getLogger("tph")

CONFIG_FILE = Path("/run/tph.json")
NFT_CONF_FILE = Path("/run/tph/tph.nft")

DEFAULT_CONFIG = {"br_if": "", "hijack_nets": []}


def run_cmd(cmd: str) -> str:
    res = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    return res.stdout.strip()


def get_permanent_mac(ifname: str) -> str:
    out = run_cmd(f"ethtool -P {ifname}")
    if "Permanent address:" in out:
        mac = out.split("Permanent address:")[1].strip().lower()
        if mac and mac != "00:00:00:00:00:00":
            return mac
    path = Path(f"/sys/class/net/{ifname}/address")
    return path.read_text().strip().lower() if path.exists() else ""


def get_current_mac(ifname: str) -> str:
    path = Path(f"/sys/class/net/{ifname}/address")
    return path.read_text().strip().lower() if path.exists() else ""


def get_default_gateway_ip(br_if: str) -> str:
    out = run_cmd(f"ip -4 -j route show default dev {br_if}")
    try:
        routes = json.loads(out)
        if routes and "gateway" in routes[0]:
            return routes[0]["gateway"]
    except (json.JSONDecodeError, IndexError):
        pass
    return ""


def get_gateway_mac(br_if: str, gw_ip: str) -> str:
    if not gw_ip:
        return ""
    run_cmd(f"arping -c 1 -w 1 -I {br_if} {gw_ip}")
    out = run_cmd(f"ip -4 -j neigh show {gw_ip} dev {br_if}")
    try:
        neighs = json.loads(out)
        if neighs and "lladdr" in neighs[0]:
            return neighs[0]["lladdr"].lower()
    except (json.JSONDecodeError, IndexError):
        pass
    return ""


def detect_wan_and_lan_ports(br_if: str, gw_mac: str):
    brif_dir = Path(f"/sys/class/net/{br_if}/brif")
    if not brif_dir.exists():
        return "", []
    all_members = sorted(p.name for p in brif_dir.iterdir())
    if not all_members or not gw_mac:
        return "", []
    wan_if = ""
    out = run_cmd(f"bridge -j fdb show br {br_if}")
    try:
        for entry in json.loads(out):
            if (entry.get("mac", "").lower() == gw_mac
                    and entry.get("master") != "self"):
                ifname = entry.get("ifname", "")
                if ifname in all_members:
                    wan_if = ifname
                    break
    except json.JSONDecodeError:
        pass
    if not wan_if:
        return "", []
    return wan_if, [i for i in all_members if i != wan_if]


def sync_bridge_mac(br_if: str, wan_if: str) -> str:
    wan_mac = get_permanent_mac(wan_if)
    br_mac = get_current_mac(br_if)
    if wan_mac and br_mac != wan_mac:
        Log.info("sync %s MAC to WAN %s physical %s", br_if, wan_if, wan_mac)
        run_cmd(f"ip link set dev {br_if} address {wan_mac}")
    return wan_mac


def apply_nft_rules(wan_if, lan_ifs, br_mac, gw_mac, hijack_nets):
    lan = ", ".join(f'"{i}"' for i in lan_ifs) if lan_ifs else '"none"'
    nets = ", ".join(hijack_nets)
    set_body = f"elements = {{ {nets} }}" if nets else ""
    nft_script = f"""
table bridge tph_shield {{
    set HIJACK_NETS {{
        type ipv4_addr
        flags interval
        auto-merge
        {set_body}
    }}

    chain STORM_SHIELD {{
        type filter hook prerouting priority -300; policy accept;
        ether type != {{ ip, arp }} counter drop
        ether type arp limit rate over 50/second burst 100 packets counter drop
        meta pkttype {{ broadcast, multicast }} limit rate over 100/second burst 200 packets counter drop
        iifname "{wan_if}" ether saddr {br_mac} counter drop
    }}

    chain HIJACK_TO_L3 {{
        type filter hook prerouting priority -100; policy accept;
        iifname {{ {lan} }} ether daddr {gw_mac} ip saddr @HIJACK_NETS \\
            meta pkttype set unicast ether daddr set {br_mac} counter accept
    }}
}}
"""
    NFT_CONF_FILE.parent.mkdir(parents=True, exist_ok=True)
    NFT_CONF_FILE.write_text(nft_script, encoding="utf-8")
    run_cmd("nft delete table bridge tph_shield 2>/dev/null")
    run_cmd(f"nft -f {NFT_CONF_FILE}")
    Log.info("tph applied | WAN=%s (%s) | LAN=%s | GW=%s | NETS=%s",
             wan_if, br_mac, lan_ifs, gw_mac, hijack_nets)


def main() -> None:
    bypass = "/usr/bin/bypass1168"
    if Path(bypass).exists():
        run_cmd(f"{bypass} --set pwon 0 1 0")
    run_cmd("sysctl -w net.bridge.bridge-nf-call-iptables=0")
    last_state = None
    while True:
        try:
            cfg = (json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
                   if CONFIG_FILE.exists() else DEFAULT_CONFIG)
            br_if = cfg.get("br_if", "")
            hijack_nets = sorted(cfg.get("hijack_nets", []))
            if not br_if:
                time.sleep(10)
                continue
            gw_ip = get_default_gateway_ip(br_if)
            gw_mac = get_gateway_mac(br_if, gw_ip)
            wan_if, lan_ifs = detect_wan_and_lan_ports(br_if, gw_mac)
            if wan_if and lan_ifs and gw_mac:
                br_mac = sync_bridge_mac(br_if, wan_if)
                state = (wan_if, tuple(lan_ifs), br_mac, gw_mac,
                         tuple(hijack_nets))
                if state != last_state:
                    apply_nft_rules(wan_if, lan_ifs, br_mac, gw_mac,
                                    hijack_nets)
                    last_state = state
            else:
                Log.warning("waiting topology | gw_ip=%s gw_mac=%s wan=%s "
                            "lan=%s", gw_ip, gw_mac, wan_if, lan_ifs)
        except Exception as e:  # noqa: BLE001
            Log.error("monitor loop: %s", e)
        time.sleep(10)


if __name__ == "__main__":
    main()
