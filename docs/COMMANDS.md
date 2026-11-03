# vyoscli 命令参考

> 本文件由 `python3 scripts/gen-command-reference.py` 从 `config_tree.py` 生成，请勿手改。

所有 `set` 命令都有对应的 `delete <path>`；`edit <path>` 进入子节点后可以省略前缀。
配置命令在 `configure` 之后执行，`commit` 生效。

## set container

| 命令 | 说明 | 示例 |
|---|---|---|
| `container <name> command` | Override container command | `container <name> command text` |
| `container <name> environment <VAR> value` | Variable value | `container <name> environment <VAR> value text` |
| `container <name> image` | Container image (e.g. nginx:alpine) | `container <name> image text` |
| `container <name> network` | podman network name | `container <name> network text` |
| `container <name> port` | Port mapping host:container (repeatable) | `container <name> port text` |
| `container <name> restart` | Restart policy: always\|on-failure\|no | `container <name> restart always` |
| `container <name> volume` | Bind mount host:container (repeatable) | `container <name> volume text` |

## set firewall

| 命令 | 说明 | 示例 |
|---|---|---|
| `firewall forwarding <name> dest` | Destination zone | `firewall forwarding <name> dest text` |
| `firewall forwarding <name> src` | Source zone | `firewall forwarding <name> src text` |
| `firewall global-options all-ping` | Respond to ICMP echo (ping) | `firewall global-options all-ping true` |
| `firewall global-options broadcast-ping` | Allow broadcast ping | `firewall global-options broadcast-ping true` |
| `firewall global-options log-martians` | Log packets with impossible addresses | `firewall global-options log-martians true` |
| `firewall global-options state-policy established` | ACCEPT/DROP | `firewall global-options state-policy established ACCEPT` |
| `firewall global-options state-policy invalid` | ACCEPT/DROP | `firewall global-options state-policy invalid ACCEPT` |
| `firewall global-options state-policy related` | ACCEPT/DROP | `firewall global-options state-policy related ACCEPT` |
| `firewall global-options syn-cookies` | Enable SYN cookies | `firewall global-options syn-cookies true` |
| `firewall group address-group <name> address` | Address or prefix | `firewall group address-group <name> address 192.0.2.1/24` |
| `firewall group interface-group <name> interface` | Interface name | `firewall group interface-group <name> interface text` |
| `firewall group ipv6-address-group <name> address` | Address or prefix | `firewall group ipv6-address-group <name> address <value>` |
| `firewall group port-group <name> port` | Port | `firewall group port-group <name> port 8080` |
| `firewall ipv4 forward filter rule <id> action` | accept \| drop \| reject | `firewall ipv4 forward filter rule <id> action text` |
| `firewall ipv4 forward filter rule <id> destination address` | Destination prefix | `firewall ipv4 forward filter rule <id> destination address 192.0.2.1/24` |
| `firewall ipv4 forward filter rule <id> destination port` | Destination port | `firewall ipv4 forward filter rule <id> destination port 8080` |
| `firewall ipv4 forward filter rule <id> destination port-group` | Port group name | `firewall ipv4 forward filter rule <id> destination port-group text` |
| `firewall ipv4 forward filter rule <id> disable` | Disable this rule | `firewall ipv4 forward filter rule <id> disable true` |
| `firewall ipv4 forward filter rule <id> inbound-interface` | Inbound interface name | `firewall ipv4 forward filter rule <id> inbound-interface text` |
| `firewall ipv4 forward filter rule <id> log` | Log matching packets | `firewall ipv4 forward filter rule <id> log true` |
| `firewall ipv4 forward filter rule <id> protocol` | tcp \| udp \| icmp \| any | `firewall ipv4 forward filter rule <id> protocol text` |
| `firewall ipv4 forward filter rule <id> source address` | Source prefix | `firewall ipv4 forward filter rule <id> source address 192.0.2.1/24` |
| `firewall ipv4 forward filter rule <id> source address-group` | Address group name | `firewall ipv4 forward filter rule <id> source address-group text` |
| `firewall ipv4 forward filter rule <id> state` | new \| established \| related \| invalid | `firewall ipv4 forward filter rule <id> state text` |
| `firewall ipv4 input filter rule <id> action` | accept \| drop \| reject | `firewall ipv4 input filter rule <id> action text` |
| `firewall ipv4 input filter rule <id> destination address` | Destination prefix | `firewall ipv4 input filter rule <id> destination address 192.0.2.1/24` |
| `firewall ipv4 input filter rule <id> destination port` | Destination port | `firewall ipv4 input filter rule <id> destination port 8080` |
| `firewall ipv4 input filter rule <id> destination port-group` | Port group name | `firewall ipv4 input filter rule <id> destination port-group text` |
| `firewall ipv4 input filter rule <id> disable` | Disable this rule | `firewall ipv4 input filter rule <id> disable true` |
| `firewall ipv4 input filter rule <id> inbound-interface` | Inbound interface name | `firewall ipv4 input filter rule <id> inbound-interface text` |
| `firewall ipv4 input filter rule <id> log` | Log matching packets | `firewall ipv4 input filter rule <id> log true` |
| `firewall ipv4 input filter rule <id> protocol` | tcp \| udp \| icmp \| any | `firewall ipv4 input filter rule <id> protocol text` |
| `firewall ipv4 input filter rule <id> source address` | Source prefix | `firewall ipv4 input filter rule <id> source address 192.0.2.1/24` |
| `firewall ipv4 input filter rule <id> source address-group` | Address group name | `firewall ipv4 input filter rule <id> source address-group text` |
| `firewall ipv4 input filter rule <id> state` | new \| established \| related \| invalid | `firewall ipv4 input filter rule <id> state text` |
| `firewall ipv4 output filter rule <id> action` | accept \| drop \| reject | `firewall ipv4 output filter rule <id> action text` |
| `firewall ipv4 output filter rule <id> destination address` | Destination prefix | `firewall ipv4 output filter rule <id> destination address 192.0.2.1/24` |
| `firewall ipv4 output filter rule <id> destination port` | Destination port | `firewall ipv4 output filter rule <id> destination port 8080` |
| `firewall ipv4 output filter rule <id> destination port-group` | Port group name | `firewall ipv4 output filter rule <id> destination port-group text` |
| `firewall ipv4 output filter rule <id> disable` | Disable this rule | `firewall ipv4 output filter rule <id> disable true` |
| `firewall ipv4 output filter rule <id> inbound-interface` | Inbound interface name | `firewall ipv4 output filter rule <id> inbound-interface text` |
| `firewall ipv4 output filter rule <id> log` | Log matching packets | `firewall ipv4 output filter rule <id> log true` |
| `firewall ipv4 output filter rule <id> protocol` | tcp \| udp \| icmp \| any | `firewall ipv4 output filter rule <id> protocol text` |
| `firewall ipv4 output filter rule <id> source address` | Source prefix | `firewall ipv4 output filter rule <id> source address 192.0.2.1/24` |
| `firewall ipv4 output filter rule <id> source address-group` | Address group name | `firewall ipv4 output filter rule <id> source address-group text` |
| `firewall ipv4 output filter rule <id> state` | new \| established \| related \| invalid | `firewall ipv4 output filter rule <id> state text` |
| `firewall ipv6 forward filter rule <id> action` | accept \| drop \| reject | `firewall ipv6 forward filter rule <id> action text` |
| `firewall ipv6 forward filter rule <id> destination address` | Destination prefix | `firewall ipv6 forward filter rule <id> destination address <value>` |
| `firewall ipv6 forward filter rule <id> destination port` | Destination port | `firewall ipv6 forward filter rule <id> destination port 8080` |
| `firewall ipv6 forward filter rule <id> destination port-group` | Port group name | `firewall ipv6 forward filter rule <id> destination port-group text` |
| `firewall ipv6 forward filter rule <id> disable` | Disable this rule | `firewall ipv6 forward filter rule <id> disable true` |
| `firewall ipv6 forward filter rule <id> inbound-interface` | Inbound interface name | `firewall ipv6 forward filter rule <id> inbound-interface text` |
| `firewall ipv6 forward filter rule <id> log` | Log matching packets | `firewall ipv6 forward filter rule <id> log true` |
| `firewall ipv6 forward filter rule <id> protocol` | tcp \| udp \| icmp \| any | `firewall ipv6 forward filter rule <id> protocol text` |
| `firewall ipv6 forward filter rule <id> source address` | Source prefix | `firewall ipv6 forward filter rule <id> source address <value>` |
| `firewall ipv6 forward filter rule <id> source address-group` | Address group name | `firewall ipv6 forward filter rule <id> source address-group text` |
| `firewall ipv6 forward filter rule <id> state` | new \| established \| related \| invalid | `firewall ipv6 forward filter rule <id> state text` |
| `firewall ipv6 input filter rule <id> action` | accept \| drop \| reject | `firewall ipv6 input filter rule <id> action text` |
| `firewall ipv6 input filter rule <id> destination address` | Destination prefix | `firewall ipv6 input filter rule <id> destination address <value>` |
| `firewall ipv6 input filter rule <id> destination port` | Destination port | `firewall ipv6 input filter rule <id> destination port 8080` |
| `firewall ipv6 input filter rule <id> destination port-group` | Port group name | `firewall ipv6 input filter rule <id> destination port-group text` |
| `firewall ipv6 input filter rule <id> disable` | Disable this rule | `firewall ipv6 input filter rule <id> disable true` |
| `firewall ipv6 input filter rule <id> inbound-interface` | Inbound interface name | `firewall ipv6 input filter rule <id> inbound-interface text` |
| `firewall ipv6 input filter rule <id> log` | Log matching packets | `firewall ipv6 input filter rule <id> log true` |
| `firewall ipv6 input filter rule <id> protocol` | tcp \| udp \| icmp \| any | `firewall ipv6 input filter rule <id> protocol text` |
| `firewall ipv6 input filter rule <id> source address` | Source prefix | `firewall ipv6 input filter rule <id> source address <value>` |
| `firewall ipv6 input filter rule <id> source address-group` | Address group name | `firewall ipv6 input filter rule <id> source address-group text` |
| `firewall ipv6 input filter rule <id> state` | new \| established \| related \| invalid | `firewall ipv6 input filter rule <id> state text` |
| `firewall ipv6 output filter rule <id> action` | accept \| drop \| reject | `firewall ipv6 output filter rule <id> action text` |
| `firewall ipv6 output filter rule <id> destination address` | Destination prefix | `firewall ipv6 output filter rule <id> destination address <value>` |
| `firewall ipv6 output filter rule <id> destination port` | Destination port | `firewall ipv6 output filter rule <id> destination port 8080` |
| `firewall ipv6 output filter rule <id> destination port-group` | Port group name | `firewall ipv6 output filter rule <id> destination port-group text` |
| `firewall ipv6 output filter rule <id> disable` | Disable this rule | `firewall ipv6 output filter rule <id> disable true` |
| `firewall ipv6 output filter rule <id> inbound-interface` | Inbound interface name | `firewall ipv6 output filter rule <id> inbound-interface text` |
| `firewall ipv6 output filter rule <id> log` | Log matching packets | `firewall ipv6 output filter rule <id> log true` |
| `firewall ipv6 output filter rule <id> protocol` | tcp \| udp \| icmp \| any | `firewall ipv6 output filter rule <id> protocol text` |
| `firewall ipv6 output filter rule <id> source address` | Source prefix | `firewall ipv6 output filter rule <id> source address <value>` |
| `firewall ipv6 output filter rule <id> source address-group` | Address group name | `firewall ipv6 output filter rule <id> source address-group text` |
| `firewall ipv6 output filter rule <id> state` | new \| established \| related \| invalid | `firewall ipv6 output filter rule <id> state text` |
| `firewall rule <id> dest-port` | Destination port | `firewall rule <id> dest-port 8080` |
| `firewall rule <id> name` | Rule name | `firewall rule <id> name text` |
| `firewall rule <id> src` | Source zone (default *) | `firewall rule <id> src text` |
| `firewall rule <id> target` | ACCEPT/DROP/REJECT | `firewall rule <id> target ACCEPT` |
| `firewall zone <zone> forward` | Default forward policy: ACCEPT/DROP/REJECT | `firewall zone <zone> forward ACCEPT` |
| `firewall zone <zone> input` | Default input policy: ACCEPT/DROP/REJECT | `firewall zone <zone> input ACCEPT` |
| `firewall zone <zone> network` | UCI network name bound to zone | `firewall zone <zone> network text` |
| `firewall zone <zone> output` | Default output policy: ACCEPT/DROP/REJECT | `firewall zone <zone> output ACCEPT` |

## set interfaces

| 命令 | 说明 | 示例 |
|---|---|---|
| `interfaces bridge <br-name> address` | IP address/prefix | `interfaces bridge <br-name> address 192.0.2.1/24` |
| `interfaces bridge <br-name> aging` | MAC aging interval (default 300) | `interfaces bridge <br-name> aging 100` |
| `interfaces bridge <br-name> description` | Description | `interfaces bridge <br-name> description text` |
| `interfaces bridge <br-name> disable` | Administratively disable | `interfaces bridge <br-name> disable true` |
| `interfaces bridge <br-name> enable-vlan` | Enable VLAN aware bridge | `interfaces bridge <br-name> enable-vlan true` |
| `interfaces bridge <br-name> forwarding-delay` | Forwarding delay (default 14) | `interfaces bridge <br-name> forwarding-delay 100` |
| `interfaces bridge <br-name> hello-time` | Hello time (default 2) | `interfaces bridge <br-name> hello-time 100` |
| `interfaces bridge <br-name> mac` | MAC address | `interfaces bridge <br-name> mac text` |
| `interfaces bridge <br-name> mac-rebinding` | Enable transparent bridge (bump-in-the-wire) | `interfaces bridge <br-name> mac-rebinding true` |
| `interfaces bridge <br-name> max-age` | Max age (default 20) | `interfaces bridge <br-name> max-age 100` |
| `interfaces bridge <br-name> member` | Bridge member interfaces | `interfaces bridge <br-name> member text` |
| `interfaces bridge <br-name> mtu` | MTU (default 1500) | `interfaces bridge <br-name> mtu 100` |
| `interfaces bridge <br-name> priority` | Bridge priority (default 32768) | `interfaces bridge <br-name> priority 100` |
| `interfaces bridge <br-name> stp` | Enable spanning tree protocol | `interfaces bridge <br-name> stp true` |
| `interfaces bridge <br-name> vlan <name> tagged` | Tagged port (repeatable) | `interfaces bridge <br-name> vlan <name> tagged text` |
| `interfaces bridge <br-name> vlan <name> untagged` | Untagged port (repeatable) | `interfaces bridge <br-name> vlan <name> untagged text` |
| `interfaces bridge <br-name> vrf` | VRF instance name | `interfaces bridge <br-name> vrf text` |
| `interfaces dummy <dum-name> address` | IP address/prefix | `interfaces dummy <dum-name> address 192.0.2.1/24` |
| `interfaces dummy <dum-name> description` | Description | `interfaces dummy <dum-name> description text` |
| `interfaces dummy <dum-name> disable` | Administratively disable | `interfaces dummy <dum-name> disable true` |
| `interfaces dummy <dum-name> mac` | MAC address | `interfaces dummy <dum-name> mac text` |
| `interfaces dummy <dum-name> mtu` | MTU (default 1500) | `interfaces dummy <dum-name> mtu 100` |
| `interfaces dummy <dum-name> vrf` | VRF instance name | `interfaces dummy <dum-name> vrf text` |
| `interfaces ethernet <ifname> address` | IPv4 address/prefix | `interfaces ethernet <ifname> address 192.0.2.1/24` |
| `interfaces ethernet <ifname> description` | Interface description | `interfaces ethernet <ifname> description text` |
| `interfaces ethernet <ifname> disable` | Administratively disable | `interfaces ethernet <ifname> disable true` |
| `interfaces ethernet <ifname> duplex` | Duplex mode: auto\|half\|full | `interfaces ethernet <ifname> duplex text` |
| `interfaces ethernet <ifname> mac` | MAC address | `interfaces ethernet <ifname> mac text` |
| `interfaces ethernet <ifname> mtu` | MTU (default 1500) | `interfaces ethernet <ifname> mtu 100` |
| `interfaces ethernet <ifname> speed` | Speed: auto\|10\|100\|1000\|2500\|10000 | `interfaces ethernet <ifname> speed text` |
| `interfaces ethernet <ifname> vif <vlan-id> address` | IPv4 address/prefix | `interfaces ethernet <ifname> vif <vlan-id> address 192.0.2.1/24` |
| `interfaces ethernet <ifname> vif <vlan-id> description` | Interface description | `interfaces ethernet <ifname> vif <vlan-id> description text` |
| `interfaces ethernet <ifname> vrf` | VRF instance name | `interfaces ethernet <ifname> vrf text` |
| `interfaces lan device` | Physical NIC for lan (e.g. eth0) | `interfaces lan device text` |
| `interfaces loopback <lo> address` | IP address/prefix | `interfaces loopback <lo> address 192.0.2.1/24` |
| `interfaces loopback <lo> description` | Description | `interfaces loopback <lo> description text` |
| `interfaces openvpn <vtun-name> ca` | CA cert path | `interfaces openvpn <vtun-name> ca text` |
| `interfaces openvpn <vtun-name> cert` | Server cert path | `interfaces openvpn <vtun-name> cert text` |
| `interfaces openvpn <vtun-name> dev` | tun\|tap | `interfaces openvpn <vtun-name> dev text` |
| `interfaces openvpn <vtun-name> dh` | DH pem path | `interfaces openvpn <vtun-name> dh text` |
| `interfaces openvpn <vtun-name> key` | Server key path | `interfaces openvpn <vtun-name> key text` |
| `interfaces openvpn <vtun-name> mode` | server\|client | `interfaces openvpn <vtun-name> mode server` |
| `interfaces openvpn <vtun-name> port` | Listen port | `interfaces openvpn <vtun-name> port 8080` |
| `interfaces openvpn <vtun-name> proto` | udp\|tcp | `interfaces openvpn <vtun-name> proto text` |
| `interfaces openvpn <vtun-name> push` | Push option to client (repeatable) | `interfaces openvpn <vtun-name> push text` |
| `interfaces openvpn <vtun-name> server` | VPN pool: x.x.x.x 255.255.255.0 | `interfaces openvpn <vtun-name> server text` |
| `interfaces tunnel <tun-name> address` | Inner tunnel IPv4/prefix | `interfaces tunnel <tun-name> address 192.0.2.1/24` |
| `interfaces tunnel <tun-name> description` | Description | `interfaces tunnel <tun-name> description text` |
| `interfaces tunnel <tun-name> disable` | Administratively disable | `interfaces tunnel <tun-name> disable true` |
| `interfaces tunnel <tun-name> encapsulation` | gre \| ipip \| sit \| ip6ip6 | `interfaces tunnel <tun-name> encapsulation gre` |
| `interfaces tunnel <tun-name> local-ip` | Source outer IP (legacy alias) | `interfaces tunnel <tun-name> local-ip 192.0.2.1` |
| `interfaces tunnel <tun-name> mtu` | MTU (default 1476) | `interfaces tunnel <tun-name> mtu 100` |
| `interfaces tunnel <tun-name> remote` | Tunnel remote address | `interfaces tunnel <tun-name> remote 192.0.2.1` |
| `interfaces tunnel <tun-name> remote-ip` | Tunnel remote address (legacy alias) | `interfaces tunnel <tun-name> remote-ip 192.0.2.1` |
| `interfaces tunnel <tun-name> source-address` | Source outer IP | `interfaces tunnel <tun-name> source-address 192.0.2.1` |
| `interfaces tunnel <tun-name> source-interface` | Source interface | `interfaces tunnel <tun-name> source-interface text` |
| `interfaces tunnel <tun-name> vrf` | VRF instance name | `interfaces tunnel <tun-name> vrf text` |
| `interfaces vxlan <vx-name> address` | Inner tunnel IPv4/prefix | `interfaces vxlan <vx-name> address 192.0.2.1/24` |
| `interfaces vxlan <vx-name> local-ip` | Local outer IPv4 | `interfaces vxlan <vx-name> local-ip 192.0.2.1` |
| `interfaces vxlan <vx-name> remote-ip` | Remote outer IPv4 | `interfaces vxlan <vx-name> remote-ip 192.0.2.1` |
| `interfaces vxlan <vx-name> vni` | VXLAN Network Identifier (1-16777215) | `interfaces vxlan <vx-name> vni text` |
| `interfaces wan device` | Physical NIC for wan (e.g. eth0) | `interfaces wan device text` |
| `interfaces wireguard <wg-if> address` | VPN address/prefix (repeatable) | `interfaces wireguard <wg-if> address 192.0.2.1/24` |
| `interfaces wireguard <wg-if> listen-port` | Listen UDP port | `interfaces wireguard <wg-if> listen-port 8080` |
| `interfaces wireguard <wg-if> peer <ip> allowed-ips` | Allowed IPs, e.g. 10.0.0.2/32 | `interfaces wireguard <wg-if> peer <ip> allowed-ips text` |
| `interfaces wireguard <wg-if> peer <ip> endpoint` | Endpoint host[:port] | `interfaces wireguard <wg-if> peer <ip> endpoint text` |
| `interfaces wireguard <wg-if> private-key` | WireGuard private key | `interfaces wireguard <wg-if> private-key text` |
| `interfaces wireless <wlan-name> channel` | Channel (e.g. 6, 36, 149) | `interfaces wireless <wlan-name> channel text` |
| `interfaces wireless <wlan-name> hw-mode` | 11g (2.4G) or 11a (5G) | `interfaces wireless <wlan-name> hw-mode 11g` |
| `interfaces wireless <wlan-name> mode` | AP mode (default ap) | `interfaces wireless <wlan-name> mode text` |
| `interfaces wireless <wlan-name> network` | Bridge to a logical network (default lan) | `interfaces wireless <wlan-name> network text` |
| `interfaces wireless <wlan-name> passphrase` | Wi-Fi password (8+ chars) | `interfaces wireless <wlan-name> passphrase text` |
| `interfaces wireless <wlan-name> security` | wpa2 \| wpa3 \| none | `interfaces wireless <wlan-name> security wpa2` |
| `interfaces wireless <wlan-name> ssid` | SSID broadcast name | `interfaces wireless <wlan-name> ssid text` |

## set nat

| 命令 | 说明 | 示例 |
|---|---|---|
| `nat destination rule <id> in-interface` | Incoming interface (e.g. wan) | `nat destination rule <id> in-interface text` |
| `nat destination rule <id> port` | External port | `nat destination rule <id> port 8080` |
| `nat destination rule <id> to` | Internal IP to forward to | `nat destination rule <id> to 192.0.2.1` |
| `nat source rule <id> out-interface` | Outgoing interface (e.g. wan) | `nat source rule <id> out-interface text` |
| `nat source rule <id> translation` | Translation type (masquerade) | `nat source rule <id> translation text` |

## set policy

| 命令 | 说明 | 示例 |
|---|---|---|
| `policy community-list <list-num> rule <id> action` | permit/deny | `policy community-list <list-num> rule <id> action permit` |
| `policy community-list <list-num> rule <id> description` | Description | `policy community-list <list-num> rule <id> description text` |
| `policy community-list <list-num> rule <id> regex` | Community regex | `policy community-list <list-num> rule <id> regex text` |
| `policy route-redirect <name> rule <id> dport` | Destination port to match | `policy route-redirect <name> rule <id> dport 8080` |
| `policy route-redirect <name> rule <id> redirect-to` | Redirect to IP:port | `policy route-redirect <name> rule <id> redirect-to text` |

## set protocols

| 命令 | 说明 | 示例 |
|---|---|---|
| `protocols bgp local-as` | Local AS number | `protocols bgp local-as 100` |
| `protocols bgp neighbor <name> description` | Neighbor description | `protocols bgp neighbor <name> description text` |
| `protocols bgp neighbor <name> remote-as` | Peer AS number | `protocols bgp neighbor <name> remote-as 100` |
| `protocols bgp neighbor <name> route-map-in` | Inbound route-map name | `protocols bgp neighbor <name> route-map-in text` |
| `protocols bgp neighbor <name> route-map-out` | Outbound route-map name | `protocols bgp neighbor <name> route-map-out text` |
| `protocols bgp network` | Advertise prefix (repeatable) | `protocols bgp network 203.0.113.0/24` |
| `protocols bgp peer-group <name> remote-as` | Remote AS | `protocols bgp peer-group <name> remote-as 100` |
| `protocols bgp peer-group <name> route-map-import` | Inbound route-map | `protocols bgp peer-group <name> route-map-import text` |
| `protocols bgp peer-group <name> soft-reconfiguration` | Soft reconfig inbound | `protocols bgp peer-group <name> soft-reconfiguration text` |
| `protocols bgp peer-group <name> update-source` | Update source IP | `protocols bgp peer-group <name> update-source 192.0.2.1` |
| `protocols bgp router-id` | BGP router-id | `protocols bgp router-id 10.0.0.1` |
| `protocols route-map <name> permit <name> match community community-list` | Community-list number | `protocols route-map <name> permit <name> match community community-list text` |
| `protocols route-map <name> permit <name> set community` | BGP community (e.g. 65001:100) | `protocols route-map <name> permit <name> set community text` |
| `protocols route-map <name> permit <name> set local-preference` | BGP local-preference | `protocols route-map <name> permit <name> set local-preference 100` |
| `protocols route-map <name> permit <name> set med` | BGP MED | `protocols route-map <name> permit <name> set med 100` |
| `protocols route-map <name> permit <name> set next-hop` | Set next-hop | `protocols route-map <name> permit <name> set next-hop 192.0.2.1` |
| `protocols static route <prefix> blackhole` | Silently drop packets | `protocols static route <prefix> blackhole true` |
| `protocols static route <prefix> interface` | Egress interface | `protocols static route <prefix> interface text` |
| `protocols static route <prefix> next-hop` | Next-hop gateway IPv4 | `protocols static route <prefix> next-hop 192.0.2.1` |
| `protocols static route <prefix> reject` | Send ICMP unreachable | `protocols static route <prefix> reject true` |

## set service

| 命令 | 说明 | 示例 |
|---|---|---|
| `service adguard disable` | Disable AdGuardHome | `service adguard disable true` |
| `service adguard enabled` | Enable AdGuardHome | `service adguard enabled true` |
| `service adguard listen-address` | Bind IP (default 0.0.0.0) | `service adguard listen-address 192.0.2.1` |
| `service adguard port` | DNS listen port (default 53) | `service adguard port 8080` |
| `service adguard upstream` | Upstream DNS (repeatable, configured in web UI) | `service adguard upstream text` |
| `service adguard web-port` | Web UI port (default 3000) | `service adguard web-port 8080` |
| `service console-server <device> alias` | Short alias for connect console | `service console-server <device> alias text` |
| `service console-server <device> data-bits` | Data bits (7 or 8, default 8) | `service console-server <device> data-bits 100` |
| `service console-server <device> description` | Device description | `service console-server <device> description text` |
| `service console-server <device> parity` | Parity (even\|odd\|none, default none) | `service console-server <device> parity text` |
| `service console-server <device> speed` | Baud rate (e.g. 9600, 115200) | `service console-server <device> speed 100` |
| `service console-server <device> ssh-port` | TCP port for remote console access | `service console-server <device> ssh-port 8080` |
| `service console-server <device> stop-bits` | Stop bits (1 or 2, default 1) | `service console-server <device> stop-bits 100` |
| `service crontab <job> description` | Free-text description | `service crontab <job> description text` |
| `service crontab <job> schedule` | Cron schedule: 'm h dom mon dow' | `service crontab <job> schedule 0 3 * * *` |
| `service crontab <job> script` | Script path (recommended: /etc/vyoscli/scripts/<name>.sh) | `service crontab <job> script text` |
| `service dhcp-server shared-network-name <shared-name> interface` | UCI network to serve (default: auto-detect from subnet) | `service dhcp-server shared-network-name <shared-name> interface text` |
| `service dhcp-server shared-network-name <shared-name> subnet <cidr> default-router` | Default gateway | `service dhcp-server shared-network-name <shared-name> subnet <cidr> default-router 192.0.2.1` |
| `service dhcp-server shared-network-name <shared-name> subnet <cidr> domain-name` | Domain name | `service dhcp-server shared-network-name <shared-name> subnet <cidr> domain-name text` |
| `service dhcp-server shared-network-name <shared-name> subnet <cidr> domain-search` | Domain search suffix | `service dhcp-server shared-network-name <shared-name> subnet <cidr> domain-search text` |
| `service dhcp-server shared-network-name <shared-name> subnet <cidr> lease` | Lease time in seconds | `service dhcp-server shared-network-name <shared-name> subnet <cidr> lease 100` |
| `service dhcp-server shared-network-name <shared-name> subnet <cidr> name-server` | DNS server (repeatable) | `service dhcp-server shared-network-name <shared-name> subnet <cidr> name-server 192.0.2.1` |
| `service dhcp-server shared-network-name <shared-name> subnet <cidr> range <id> start` | First address in the range | `service dhcp-server shared-network-name <shared-name> subnet <cidr> range <id> start 192.0.2.1` |
| `service dhcp-server shared-network-name <shared-name> subnet <cidr> range <id> stop` | Last address in the range | `service dhcp-server shared-network-name <shared-name> subnet <cidr> range <id> stop 192.0.2.1` |
| `service dhcp-server shared-network-name <shared-name> subnet <cidr> static-mapping <name> ip-address` | Fixed IP | `service dhcp-server shared-network-name <shared-name> subnet <cidr> static-mapping <name> ip-address 192.0.2.1` |
| `service dhcp-server shared-network-name <shared-name> subnet <cidr> static-mapping <name> mac-address` | MAC address | `service dhcp-server shared-network-name <shared-name> subnet <cidr> static-mapping <name> mac-address text` |
| `service dnsmasq disable` | Disable dnsmasq | `service dnsmasq disable true` |
| `service dnsmasq listen-address` | Bind IP (default 0.0.0.0) | `service dnsmasq listen-address 192.0.2.1` |
| `service dnsmasq port` | DNS listen port (default 53) | `service dnsmasq port 8080` |
| `service kcp <tunnel> kcp-mode` | fast2/fast3/normal | `service kcp <tunnel> kcp-mode fast3` |
| `service kcp <tunnel> local-ip` | Local listen IP | `service kcp <tunnel> local-ip 192.0.2.1` |
| `service kcp <tunnel> local-port` | Local listen port | `service kcp <tunnel> local-port 8080` |
| `service kcp <tunnel> mode` | c/client or s/server | `service kcp <tunnel> mode c` |
| `service kcp <tunnel> remote-ip` | Remote IP | `service kcp <tunnel> remote-ip 192.0.2.1` |
| `service kcp <tunnel> remote-port` | Remote port | `service kcp <tunnel> remote-port 8080` |
| `service smartdns address <domain> ip` | Answer IP | `service smartdns address <domain> ip 192.0.2.1` |
| `service smartdns disable` | Disable smartdns | `service smartdns disable true` |
| `service smartdns domain-rule <name> domain-set` | Which domain-set to match | `service smartdns domain-rule <name> domain-set text` |
| `service smartdns domain-rule <name> forward` | Upstream server name (repeatable) | `service smartdns domain-rule <name> forward text` |
| `service smartdns domain-set <name> domain` | Add a domain to the set | `service smartdns domain-set <name> domain text` |
| `service smartdns domain-set <name> file` | Domain list file (recommended: /etc/vyoscli/lists/<name>.txt) | `service smartdns domain-set <name> file text` |
| `service smartdns enabled` | Enable SmartDNS | `service smartdns enabled true` |
| `service smartdns forbid-aaaa` | Suppress IPv6 (AAAA) answers | `service smartdns forbid-aaaa true` |
| `service smartdns listen-address` | Bind IP (default 0.0.0.0) | `service smartdns listen-address 192.0.2.1` |
| `service smartdns port` | Listen port (default 5333) | `service smartdns port 8080` |
| `service smartdns server <name> ip` | Server IP | `service smartdns server <name> ip 192.0.2.1` |
| `service smartdns server <name> port` | Server port | `service smartdns server <name> port 8080` |
| `service smartdns server <name> type` | udp\|tcp\|tls\|https | `service smartdns server <name> type udp` |
| `service smartdns speed-check-mode` | Probe mode, e.g. 'ping,tcp:80' | `service smartdns speed-check-mode text` |
| `service sqm download` | Download bandwidth kbps | `service sqm download 100` |
| `service sqm interface` | WAN interface | `service sqm interface text` |
| `service sqm qdisc` | cake / fq_codel | `service sqm qdisc cake` |
| `service sqm upload` | Upload bandwidth kbps | `service sqm upload 100` |
| `service ssh disable` | Disable SSH server | `service ssh disable true` |
| `service ssh listen-address` | Bind address (default 0.0.0.0) | `service ssh listen-address 192.0.2.1` |
| `service ssh password-auth` | Allow password login (true/false) | `service ssh password-auth true` |
| `service ssh port` | Listen port (default 22) | `service ssh port 8080` |
| `service ssh root-login` | Allow root SSH login (true/false) | `service ssh root-login true` |
| `service tcp-accelerate congestion-control` | bbr/cubic/hybla | `service tcp-accelerate congestion-control bbr` |
| `service tcp-accelerate fq-codel` | Enable fq_codel qdisc | `service tcp-accelerate fq-codel true` |

## set system

| 命令 | 说明 | 示例 |
|---|---|---|
| `system dns` | System resolver for router itself (/etc/resolv.conf) | `system dns 192.0.2.1` |
| `system domain-search` | Domain search suffix (repeatable) | `system domain-search text` |
| `system hardware model` | Hardware model | `system hardware model text` |
| `system hardware serial` | Hardware serial number (S/N) | `system hardware serial text` |
| `system hardware vendor` | Hardware vendor name | `system hardware vendor text` |
| `system host-name` | System hostname | `system host-name edge-1` |
| `system language` | System locale (e.g. zh_cn, en) | `system language text` |
| `system login user <username> authentication encrypted-password` | Encrypted password | `system login user <username> authentication encrypted-password text` |
| `system login user <username> authentication plaintext-password` | Plain password | `system login user <username> authentication plaintext-password text` |
| `system login user <username> authentication public-keys <key-id> key` | Public key content | `system login user <username> authentication public-keys <key-id> key text` |
| `system login user <username> authentication public-keys <key-id> type` | ssh-rsa/ssh-ed25519 | `system login user <username> authentication public-keys <key-id> type ssh-ed25519` |
| `system login user <username> disable` | Disable account | `system login user <username> disable true` |
| `system login user <username> full-name` | Full name | `system login user <username> full-name text` |
| `system name-server` | Upstream DNS for dnsmasq (client queries) | `system name-server 192.0.2.1` |
| `system ntp` | NTP server hostname (repeatable) | `system ntp ntp.aliyun.com` |
| `system timezone` | IANA timezone (e.g. Asia/Shanghai) | `system timezone Asia/Shanghai` |

## set traffic-policy

| 命令 | 说明 | 示例 |
|---|---|---|
| `traffic-policy shaper <policy> bandwidth` | Total bandwidth (e.g. 100mbit) | `traffic-policy shaper <policy> bandwidth 100mbit` |
| `traffic-policy shaper <policy> interface` | Egress interface | `traffic-policy shaper <policy> interface text` |
| `traffic-policy shaper <policy> per-ip` | Per-IP bandwidth limit (e.g. 10mbit) | `traffic-policy shaper <policy> per-ip 100mbit` |

## set vpn

| 命令 | 说明 | 示例 |
|---|---|---|
| `vpn ipsec esp-group <group> lifetime` | ESP lifetime seconds | `vpn ipsec esp-group <group> lifetime 100` |
| `vpn ipsec esp-group <group> proposal <num> encryption` | aes256/aes128 | `vpn ipsec esp-group <group> proposal <num> encryption text` |
| `vpn ipsec esp-group <group> proposal <num> hash` | sha256/sha1 | `vpn ipsec esp-group <group> proposal <num> hash text` |
| `vpn ipsec ike-group <group> lifetime` | IKE lifetime seconds | `vpn ipsec ike-group <group> lifetime 100` |
| `vpn ipsec ike-group <group> proposal <num> dh-group` | DH group (14/19/20) | `vpn ipsec ike-group <group> proposal <num> dh-group 100` |
| `vpn ipsec ike-group <group> proposal <num> encryption` | aes256/aes128 | `vpn ipsec ike-group <group> proposal <num> encryption text` |
| `vpn ipsec ike-group <group> proposal <num> hash` | sha256/sha1 | `vpn ipsec ike-group <group> proposal <num> hash text` |
| `vpn ipsec remote-access dns` | DNS server for clients | `vpn ipsec remote-access dns 192.0.2.1` |
| `vpn ipsec remote-access enabled` | Enable remote access | `vpn ipsec remote-access enabled true` |
| `vpn ipsec remote-access local-id` | Server ID | `vpn ipsec remote-access local-id text` |
| `vpn ipsec remote-access pool-end` | Client pool end IP | `vpn ipsec remote-access pool-end 192.0.2.1` |
| `vpn ipsec remote-access pool-start` | Client pool start IP | `vpn ipsec remote-access pool-start 192.0.2.1` |
| `vpn ipsec remote-access secret` | PSK secret | `vpn ipsec remote-access secret text` |
| `vpn ipsec site-to-site peer <ip> esp-group` | ESP group name | `vpn ipsec site-to-site peer <ip> esp-group text` |
| `vpn ipsec site-to-site peer <ip> ike-group` | IKE group name | `vpn ipsec site-to-site peer <ip> ike-group text` |
| `vpn ipsec site-to-site peer <ip> local-address` | Local public IP | `vpn ipsec site-to-site peer <ip> local-address 192.0.2.1` |
| `vpn ipsec site-to-site peer <ip> local-id` | Local ID | `vpn ipsec site-to-site peer <ip> local-id text` |
| `vpn ipsec site-to-site peer <ip> remote-address` | Remote public IP | `vpn ipsec site-to-site peer <ip> remote-address 192.0.2.1` |
| `vpn ipsec site-to-site peer <ip> remote-id` | Remote ID | `vpn ipsec site-to-site peer <ip> remote-id text` |
| `vpn ipsec site-to-site peer <ip> secret` | PSK secret | `vpn ipsec site-to-site peer <ip> secret text` |
| `vpn ipsec site-to-site peer <ip> tunnel <tun-name> local-prefix` | Local subnet | `vpn ipsec site-to-site peer <ip> tunnel <tun-name> local-prefix 203.0.113.0/24` |
| `vpn ipsec site-to-site peer <ip> tunnel <tun-name> remote-prefix` | Remote subnet | `vpn ipsec site-to-site peer <ip> tunnel <tun-name> remote-prefix 203.0.113.0/24` |

## set vrf

| 命令 | 说明 | 示例 |
|---|---|---|
| `vrf name <vrf> table` | Routing table ID | `vrf name <vrf> table 100` |
