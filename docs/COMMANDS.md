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

## set high-availability

| 命令 | 说明 | 示例 |
|---|---|---|
| `high-availability vrrp global-parameters startup-delay` | Delay before starting VRRP (s) | `high-availability vrrp global-parameters startup-delay 100` |
| `high-availability vrrp group <name> address` | Virtual IP address | `high-availability vrrp group <name> address 192.0.2.1/24` |
| `high-availability vrrp group <name> hello-source-address` | Unicast source address | `high-availability vrrp group <name> hello-source-address 192.0.2.1` |
| `high-availability vrrp group <name> interface` | VRRP interface | `high-availability vrrp group <name> interface text` |
| `high-availability vrrp group <name> no-preempt` | Disable preemption | `high-availability vrrp group <name> no-preempt true` |
| `high-availability vrrp group <name> peer-address` | Unicast peer address | `high-availability vrrp group <name> peer-address 192.0.2.1` |
| `high-availability vrrp group <name> preempt-delay` | Preemption delay (s) | `high-availability vrrp group <name> preempt-delay 100` |
| `high-availability vrrp group <name> priority` | Priority (1-255) | `high-availability vrrp group <name> priority 100` |
| `high-availability vrrp group <name> track interface` | Interface to track | `high-availability vrrp group <name> track interface text` |
| `high-availability vrrp group <name> vrid` | Virtual router ID (1-255) | `high-availability vrrp group <name> vrid 100` |
| `high-availability vrrp sync-group <name> member` | Member VRRP group | `high-availability vrrp sync-group <name> member text` |

## set interfaces

| 命令 | 说明 | 示例 |
|---|---|---|
| `interfaces bonding <name> address` | IPv4 address/prefix | `interfaces bonding <name> address 192.0.2.1/24` |
| `interfaces bonding <name> description` | Description | `interfaces bonding <name> description text` |
| `interfaces bonding <name> disable` | Administratively disable | `interfaces bonding <name> disable true` |
| `interfaces bonding <name> hash-policy` | xmit hash policy (layer2+3, layer3+4) | `interfaces bonding <name> hash-policy text` |
| `interfaces bonding <name> member` | Member interface | `interfaces bonding <name> member text` |
| `interfaces bonding <name> mode` | 802.3ad \| active-backup \| balance-rr \| ... | `interfaces bonding <name> mode text` |
| `interfaces bonding <name> mtu` | MTU | `interfaces bonding <name> mtu 100` |
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
| `interfaces geneve <name> address` | Inner IPv4/prefix | `interfaces geneve <name> address 192.0.2.1/24` |
| `interfaces geneve <name> description` | Description | `interfaces geneve <name> description text` |
| `interfaces geneve <name> disable` | Administratively disable | `interfaces geneve <name> disable true` |
| `interfaces geneve <name> mtu` | MTU | `interfaces geneve <name> mtu 100` |
| `interfaces geneve <name> remote` | Remote VTEP | `interfaces geneve <name> remote 192.0.2.1` |
| `interfaces geneve <name> vni` | VXLAN/Geneve network identifier | `interfaces geneve <name> vni 100` |
| `interfaces lan device` | Physical NIC for lan (e.g. eth0) | `interfaces lan device text` |
| `interfaces loopback <lo> address` | IP address/prefix | `interfaces loopback <lo> address 192.0.2.1/24` |
| `interfaces loopback <lo> description` | Description | `interfaces loopback <lo> description text` |
| `interfaces macsec <name> address` | IPv4 address/prefix | `interfaces macsec <name> address 192.0.2.1/24` |
| `interfaces macsec <name> cipher` | gcm-aes-128 \| gcm-aes-256 | `interfaces macsec <name> cipher text` |
| `interfaces macsec <name> description` | Description | `interfaces macsec <name> description text` |
| `interfaces macsec <name> disable` | Administratively disable | `interfaces macsec <name> disable true` |
| `interfaces macsec <name> key` | TX SAK (16/32 hex bytes) | `interfaces macsec <name> key text` |
| `interfaces macsec <name> mtu` | MTU | `interfaces macsec <name> mtu 100` |
| `interfaces macsec <name> source-interface` | Underlying interface | `interfaces macsec <name> source-interface text` |
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
| `interfaces pppoe <name> access-concentrator` | Target access concentrator | `interfaces pppoe <name> access-concentrator text` |
| `interfaces pppoe <name> authentication password` | ISP password | `interfaces pppoe <name> authentication password text` |
| `interfaces pppoe <name> authentication username` | ISP username | `interfaces pppoe <name> authentication username text` |
| `interfaces pppoe <name> default-route-distance` | Distance for the ISP default route | `interfaces pppoe <name> default-route-distance 100` |
| `interfaces pppoe <name> description` | Description | `interfaces pppoe <name> description text` |
| `interfaces pppoe <name> disable` | Administratively disable | `interfaces pppoe <name> disable true` |
| `interfaces pppoe <name> holdoff` | Redial delay in seconds | `interfaces pppoe <name> holdoff 100` |
| `interfaces pppoe <name> mru` | MRU (default 1492) | `interfaces pppoe <name> mru 100` |
| `interfaces pppoe <name> mtu` | MTU (default 1492) | `interfaces pppoe <name> mtu 100` |
| `interfaces pppoe <name> no-default-route` | Do not install the ISP default route | `interfaces pppoe <name> no-default-route true` |
| `interfaces pppoe <name> no-peer-dns` | Ignore ISP-provided DNS servers | `interfaces pppoe <name> no-peer-dns true` |
| `interfaces pppoe <name> service-name` | Service name | `interfaces pppoe <name> service-name text` |
| `interfaces pppoe <name> source-interface` | Underlying interface (e.g. eth0) | `interfaces pppoe <name> source-interface text` |
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
| `interfaces vti <name> address` | Inner IPv4/prefix | `interfaces vti <name> address 192.0.2.1/24` |
| `interfaces vti <name> description` | Description | `interfaces vti <name> description text` |
| `interfaces vti <name> disable` | Administratively disable | `interfaces vti <name> disable true` |
| `interfaces vti <name> key` | VTI key | `interfaces vti <name> key 100` |
| `interfaces vti <name> local-ip` | Local outer address | `interfaces vti <name> local-ip 192.0.2.1` |
| `interfaces vti <name> mtu` | MTU | `interfaces vti <name> mtu 100` |
| `interfaces vti <name> remote` | Remote outer address | `interfaces vti <name> remote 192.0.2.1` |
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

## set load-balancing

| 命令 | 说明 | 示例 |
|---|---|---|
| `load-balancing haproxy backend <name> balance` | roundrobin \| leastconn \| source | `load-balancing haproxy backend <name> balance text` |
| `load-balancing haproxy backend <name> server <name> address` | Server address | `load-balancing haproxy backend <name> server <name> address 192.0.2.1` |
| `load-balancing haproxy backend <name> server <name> check` | Enable health checks | `load-balancing haproxy backend <name> server <name> check true` |
| `load-balancing haproxy backend <name> server <name> port` | Server port | `load-balancing haproxy backend <name> server <name> port 8080` |
| `load-balancing haproxy backend <name> server <name> weight` | Server weight | `load-balancing haproxy backend <name> server <name> weight 100` |
| `load-balancing haproxy global-parameters max-connections` | Maximum connections | `load-balancing haproxy global-parameters max-connections 100` |
| `load-balancing haproxy service <name> backend` | Backend name | `load-balancing haproxy service <name> backend text` |
| `load-balancing haproxy service <name> listen-address` | Bind address | `load-balancing haproxy service <name> listen-address 192.0.2.1` |
| `load-balancing haproxy service <name> mode` | tcp \| http | `load-balancing haproxy service <name> mode text` |
| `load-balancing haproxy service <name> port` | Bind port | `load-balancing haproxy service <name> port 8080` |
| `load-balancing wan interface <name> track-ip` | Health-check address | `load-balancing wan interface <name> track-ip 192.0.2.1` |
| `load-balancing wan interface <name> weight` | Load-balancing weight | `load-balancing wan interface <name> weight 100` |
| `load-balancing wan rule <id> destination` | Destination prefix | `load-balancing wan rule <id> destination 192.0.2.1/24` |
| `load-balancing wan rule <id> interface` | Preferred interface | `load-balancing wan rule <id> interface text` |
| `load-balancing wan rule <id> source` | Source prefix | `load-balancing wan rule <id> source 192.0.2.1/24` |

## set nat

| 命令 | 说明 | 示例 |
|---|---|---|
| `nat destination rule <id> destination address` | Destination prefix | `nat destination rule <id> destination address 192.0.2.1/24` |
| `nat destination rule <id> destination port` | Destination port | `nat destination rule <id> destination port 8080` |
| `nat destination rule <id> disable` | Disable this rule | `nat destination rule <id> disable true` |
| `nat destination rule <id> hairpin` | Also match traffic from internal clients | `nat destination rule <id> hairpin true` |
| `nat destination rule <id> inbound-interface` | Incoming interface (e.g. eth0) | `nat destination rule <id> inbound-interface text` |
| `nat destination rule <id> log` | Log matching packets | `nat destination rule <id> log true` |
| `nat destination rule <id> protocol` | tcp \| udp \| any | `nat destination rule <id> protocol text` |
| `nat destination rule <id> source address` | Source prefix | `nat destination rule <id> source address 192.0.2.1/24` |
| `nat destination rule <id> source port` | Source port | `nat destination rule <id> source port 8080` |
| `nat destination rule <id> translation address` | Internal address to forward to | `nat destination rule <id> translation address 192.0.2.1` |
| `nat destination rule <id> translation port` | Translated destination port | `nat destination rule <id> translation port 8080` |
| `nat source rule <id> destination address` | Destination prefix | `nat source rule <id> destination address 192.0.2.1/24` |
| `nat source rule <id> destination port` | Destination port | `nat source rule <id> destination port 8080` |
| `nat source rule <id> disable` | Disable this rule | `nat source rule <id> disable true` |
| `nat source rule <id> log` | Log matching packets | `nat source rule <id> log true` |
| `nat source rule <id> out-interface` | Outgoing interface (e.g. eth1) | `nat source rule <id> out-interface text` |
| `nat source rule <id> protocol` | tcp \| udp \| any | `nat source rule <id> protocol text` |
| `nat source rule <id> source address` | Source prefix | `nat source rule <id> source address 192.0.2.1/24` |
| `nat source rule <id> source port` | Source port | `nat source rule <id> source port 8080` |
| `nat source rule <id> translation address` | masquerade or an IPv4 address | `nat source rule <id> translation address text` |
| `nat source rule <id> translation port` | Translated source port | `nat source rule <id> translation port 8080` |

## set nat66

| 命令 | 说明 | 示例 |
|---|---|---|
| `nat66 destination rule <id> destination address` | Destination prefix | `nat66 destination rule <id> destination address <value>` |
| `nat66 destination rule <id> destination port` | Destination port | `nat66 destination rule <id> destination port 8080` |
| `nat66 destination rule <id> disable` | Disable this rule | `nat66 destination rule <id> disable true` |
| `nat66 destination rule <id> hairpin` | Also match internal clients | `nat66 destination rule <id> hairpin true` |
| `nat66 destination rule <id> inbound-interface` | Incoming interface | `nat66 destination rule <id> inbound-interface text` |
| `nat66 destination rule <id> log` | Log matching packets | `nat66 destination rule <id> log true` |
| `nat66 destination rule <id> protocol` | tcp \| udp \| any | `nat66 destination rule <id> protocol text` |
| `nat66 destination rule <id> source address` | Source prefix | `nat66 destination rule <id> source address <value>` |
| `nat66 destination rule <id> source port` | Source port | `nat66 destination rule <id> source port 8080` |
| `nat66 destination rule <id> translation address` | Internal IPv6 address | `nat66 destination rule <id> translation address <value>` |
| `nat66 destination rule <id> translation port` | Translated destination port | `nat66 destination rule <id> translation port 8080` |
| `nat66 source rule <id> destination address` | Destination prefix | `nat66 source rule <id> destination address <value>` |
| `nat66 source rule <id> destination port` | Destination port | `nat66 source rule <id> destination port 8080` |
| `nat66 source rule <id> disable` | Disable this rule | `nat66 source rule <id> disable true` |
| `nat66 source rule <id> log` | Log matching packets | `nat66 source rule <id> log true` |
| `nat66 source rule <id> out-interface` | Outgoing interface | `nat66 source rule <id> out-interface text` |
| `nat66 source rule <id> protocol` | tcp \| udp \| any | `nat66 source rule <id> protocol text` |
| `nat66 source rule <id> source address` | Source prefix | `nat66 source rule <id> source address <value>` |
| `nat66 source rule <id> source port` | Source port | `nat66 source rule <id> source port 8080` |
| `nat66 source rule <id> translation address` | masquerade or an IPv6 address | `nat66 source rule <id> translation address text` |
| `nat66 source rule <id> translation port` | Translated source port | `nat66 source rule <id> translation port 8080` |

## set pki

| 命令 | 说明 | 示例 |
|---|---|---|
| `pki ca <name> certificate` | CA certificate (PEM, single line) | `pki ca <name> certificate text` |
| `pki ca <name> crl` | Certificate revocation list (PEM) | `pki ca <name> crl text` |
| `pki ca <name> description` | Description | `pki ca <name> description text` |
| `pki ca <name> private key` | CA private key (PEM, single line) | `pki ca <name> private key text` |
| `pki certificate <name> certificate` | Certificate (PEM, single line) | `pki certificate <name> certificate text` |
| `pki certificate <name> description` | Description | `pki certificate <name> description text` |
| `pki certificate <name> private key` | Private key (PEM, single line) | `pki certificate <name> private key text` |
| `pki key-pair <name> private key` | Private key (PEM, single line) | `pki key-pair <name> private key text` |
| `pki key-pair <name> public key` | Public key (PEM, single line) | `pki key-pair <name> public key text` |

## set policy

| 命令 | 说明 | 示例 |
|---|---|---|
| `policy access-list <name> rule <id> action` | permit \| deny | `policy access-list <name> rule <id> action text` |
| `policy access-list <name> rule <id> destination address` | Destination prefix | `policy access-list <name> rule <id> destination address 192.0.2.1/24` |
| `policy access-list <name> rule <id> destination port` | Destination port | `policy access-list <name> rule <id> destination port 8080` |
| `policy access-list <name> rule <id> protocol` | ip \| tcp \| udp \| icmp | `policy access-list <name> rule <id> protocol text` |
| `policy access-list <name> rule <id> source address` | Source prefix | `policy access-list <name> rule <id> source address 192.0.2.1/24` |
| `policy access-list <name> rule <id> source port` | Source port | `policy access-list <name> rule <id> source port 8080` |
| `policy as-path-list <name> rule <id> action` | permit \| deny | `policy as-path-list <name> rule <id> action text` |
| `policy as-path-list <name> rule <id> regex` | AS path regular expression | `policy as-path-list <name> rule <id> regex text` |
| `policy community-list <list-num> rule <id> action` | permit/deny | `policy community-list <list-num> rule <id> action permit` |
| `policy community-list <list-num> rule <id> description` | Description | `policy community-list <list-num> rule <id> description text` |
| `policy community-list <list-num> rule <id> regex` | Community regex | `policy community-list <list-num> rule <id> regex text` |
| `policy prefix-list <name> rule <id> action` | permit \| deny | `policy prefix-list <name> rule <id> action text` |
| `policy prefix-list <name> rule <id> ge` | Minimum prefix length | `policy prefix-list <name> rule <id> ge 100` |
| `policy prefix-list <name> rule <id> le` | Maximum prefix length | `policy prefix-list <name> rule <id> le 100` |
| `policy prefix-list <name> rule <id> prefix` | Prefix to match | `policy prefix-list <name> rule <id> prefix 192.0.2.1/24` |
| `policy route-redirect <name> rule <id> dport` | Destination port to match | `policy route-redirect <name> rule <id> dport 8080` |
| `policy route-redirect <name> rule <id> redirect-to` | Redirect to IP:port | `policy route-redirect <name> rule <id> redirect-to text` |

## set protocols

| 命令 | 说明 | 示例 |
|---|---|---|
| `protocols bfd interval` | Transmit interval (ms) | `protocols bfd interval 100` |
| `protocols bfd min-rx` | Minimum receive interval (ms) | `protocols bfd min-rx 100` |
| `protocols bfd multiplier` | Detection multiplier | `protocols bfd multiplier 100` |
| `protocols bgp local-as` | Local AS number | `protocols bgp local-as 100` |
| `protocols bgp neighbor <name> description` | Neighbor description | `protocols bgp neighbor <name> description text` |
| `protocols bgp neighbor <name> remote-as` | Peer AS number | `protocols bgp neighbor <name> remote-as 100` |
| `protocols bgp neighbor <name> route-map-in` | Inbound route-map name | `protocols bgp neighbor <name> route-map-in text` |
| `protocols bgp neighbor <name> route-map-out` | Outbound route-map name | `protocols bgp neighbor <name> route-map-out text` |
| `protocols bgp neighbor <name> soft-reconfiguration inbound` | Enable inbound soft reconfiguration | `protocols bgp neighbor <name> soft-reconfiguration inbound true` |
| `protocols bgp network` | Advertise prefix (repeatable) | `protocols bgp network 203.0.113.0/24` |
| `protocols bgp peer-group <name> remote-as` | Remote AS | `protocols bgp peer-group <name> remote-as 100` |
| `protocols bgp peer-group <name> route-map-import` | Inbound route-map | `protocols bgp peer-group <name> route-map-import text` |
| `protocols bgp peer-group <name> soft-reconfiguration` | Soft reconfig inbound | `protocols bgp peer-group <name> soft-reconfiguration text` |
| `protocols bgp peer-group <name> update-source` | Update source IP | `protocols bgp peer-group <name> update-source 192.0.2.1` |
| `protocols bgp router-id` | BGP router-id | `protocols bgp router-id 10.0.0.1` |
| `protocols ospf area <name> network` | Network to advertise in this area | `protocols ospf area <name> network 192.0.2.1/24` |
| `protocols ospf area <name> type` | normal \| stub \| nssa | `protocols ospf area <name> type text` |
| `protocols ospf default-information` | Originate a default route | `protocols ospf default-information true` |
| `protocols ospf interface <name> area` | Area ID | `protocols ospf interface <name> area text` |
| `protocols ospf interface <name> bfd` | Enable BFD on this interface | `protocols ospf interface <name> bfd true` |
| `protocols ospf interface <name> cost` | Interface cost | `protocols ospf interface <name> cost 100` |
| `protocols ospf interface <name> passive` | Do not form adjacencies on this interface | `protocols ospf interface <name> passive true` |
| `protocols ospf interface <name> priority` | DR election priority | `protocols ospf interface <name> priority 100` |
| `protocols ospf log-adjacency-changes` | Log adjacency changes | `protocols ospf log-adjacency-changes true` |
| `protocols ospf router-id` | OSPF router-id | `protocols ospf router-id 10.0.0.1` |
| `protocols rip default-information` | Originate a default route | `protocols rip default-information true` |
| `protocols rip network` | Network to advertise | `protocols rip network 192.0.2.1/24` |
| `protocols rip version` | RIP version (1 or 2) | `protocols rip version 100` |
| `protocols route-map <name> permit <name> match as-path` | Match an AS path list | `protocols route-map <name> permit <name> match as-path text` |
| `protocols route-map <name> permit <name> match community community-list` | Community-list number | `protocols route-map <name> permit <name> match community community-list text` |
| `protocols route-map <name> permit <name> match metric` | Match route metric | `protocols route-map <name> permit <name> match metric 100` |
| `protocols route-map <name> permit <name> match prefix-list` | Match an IPv4 prefix-list | `protocols route-map <name> permit <name> match prefix-list text` |
| `protocols route-map <name> permit <name> match tag` | Match route tag | `protocols route-map <name> permit <name> match tag 100` |
| `protocols route-map <name> permit <name> set community` | BGP community (e.g. 65001:100) | `protocols route-map <name> permit <name> set community text` |
| `protocols route-map <name> permit <name> set local-preference` | BGP local-preference | `protocols route-map <name> permit <name> set local-preference 100` |
| `protocols route-map <name> permit <name> set med` | BGP MED | `protocols route-map <name> permit <name> set med 100` |
| `protocols route-map <name> permit <name> set metric` | Set route metric | `protocols route-map <name> permit <name> set metric 100` |
| `protocols route-map <name> permit <name> set next-hop` | Set next-hop | `protocols route-map <name> permit <name> set next-hop 192.0.2.1` |
| `protocols route-map <name> permit <name> set origin` | Set BGP origin (igp\|egp\|incomplete) | `protocols route-map <name> permit <name> set origin text` |
| `protocols route-map <name> permit <name> set tag` | Set route tag | `protocols route-map <name> permit <name> set tag 100` |
| `protocols route-map <name> permit <name> set weight` | Set BGP weight | `protocols route-map <name> permit <name> set weight 100` |
| `protocols static route <prefix> blackhole` | Silently drop packets | `protocols static route <prefix> blackhole true` |
| `protocols static route <prefix> interface` | Egress interface | `protocols static route <prefix> interface text` |
| `protocols static route <prefix> next-hop` | Next-hop gateway IPv4 | `protocols static route <prefix> next-hop 192.0.2.1` |
| `protocols static route <prefix> reject` | Send ICMP unreachable | `protocols static route <prefix> reject true` |

## set qos

| 命令 | 说明 | 示例 |
|---|---|---|
| `qos interface <name> egress` | Egress policy name | `qos interface <name> egress text` |
| `qos interface <name> ingress` | Ingress policy name | `qos interface <name> ingress text` |
| `qos policy cake <name> bandwidth` | Shaping bandwidth | `qos policy cake <name> bandwidth text` |
| `qos policy cake <name> flow-isolation` | Flow isolation mode | `qos policy cake <name> flow-isolation text` |
| `qos policy cake <name> rtt` | RTT (ms) | `qos policy cake <name> rtt 100` |
| `qos policy fq-codel <name> flows` | Number of flows | `qos policy fq-codel <name> flows 100` |
| `qos policy fq-codel <name> interval` | CoDel interval (ms) | `qos policy fq-codel <name> interval 100` |
| `qos policy fq-codel <name> quantum` | Deficit quantum (bytes) | `qos policy fq-codel <name> quantum 100` |
| `qos policy fq-codel <name> queue-limit` | Queue limit (packets) | `qos policy fq-codel <name> queue-limit 100` |
| `qos policy fq-codel <name> target` | CoDel target (ms) | `qos policy fq-codel <name> target 100` |
| `qos policy limiter <name> class <name> bandwidth` | Rate limit | `qos policy limiter <name> class <name> bandwidth text` |
| `qos policy limiter <name> class <name> burst` | Burst size | `qos policy limiter <name> class <name> burst text` |
| `qos policy limiter <name> default bandwidth` | Rate limit | `qos policy limiter <name> default bandwidth text` |
| `qos policy limiter <name> default burst` | Burst size | `qos policy limiter <name> default burst text` |
| `qos policy shaper <policy> bandwidth` | Total bandwidth (e.g. 100mbit) | `qos policy shaper <policy> bandwidth 100mbit` |
| `qos policy shaper <policy> class <name> bandwidth` | Guaranteed bandwidth | `qos policy shaper <policy> class <name> bandwidth text` |
| `qos policy shaper <policy> class <name> ceiling` | Maximum bandwidth | `qos policy shaper <policy> class <name> ceiling text` |
| `qos policy shaper <policy> class <name> priority` | Priority 0-7 | `qos policy shaper <policy> class <name> priority 100` |
| `qos policy shaper <policy> class <name> queue-type` | fq-codel \| fair-queue \| drop-tail | `qos policy shaper <policy> class <name> queue-type text` |
| `qos policy shaper <policy> default bandwidth` | Default class bandwidth | `qos policy shaper <policy> default bandwidth text` |
| `qos policy shaper <policy> default queue-type` | fq-codel \| fair-queue \| drop-tail | `qos policy shaper <policy> default queue-type text` |

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
| `service dhcp-relay interface` | Client-facing interface | `service dhcp-relay interface text` |
| `service dhcp-relay server` | DHCP server address | `service dhcp-relay server 192.0.2.1` |
| `service dhcp-relay upstream-interface` | Server-facing interface | `service dhcp-relay upstream-interface text` |
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
| `service https api-key` | Bearer token required by the API | `service https api-key text` |
| `service https certificate` | pki certificate name used for TLS (enables HTTPS) | `service https certificate text` |
| `service https listen-address` | Bind address (default 127.0.0.1) | `service https listen-address 192.0.2.1` |
| `service https port` | API port (default 8443) | `service https port 8080` |
| `service kcp <tunnel> kcp-mode` | fast2/fast3/normal | `service kcp <tunnel> kcp-mode fast3` |
| `service kcp <tunnel> local-ip` | Local listen IP | `service kcp <tunnel> local-ip 192.0.2.1` |
| `service kcp <tunnel> local-port` | Local listen port | `service kcp <tunnel> local-port 8080` |
| `service kcp <tunnel> mode` | c/client or s/server | `service kcp <tunnel> mode c` |
| `service kcp <tunnel> remote-ip` | Remote IP | `service kcp <tunnel> remote-ip 192.0.2.1` |
| `service kcp <tunnel> remote-port` | Remote port | `service kcp <tunnel> remote-port 8080` |
| `service lldp description` | Description sent in LLDP frames | `service lldp description text` |
| `service lldp interface` | Interface to advertise on | `service lldp interface text` |
| `service lldp snmp` | Enable the SNMP subagent | `service lldp snmp true` |
| `service ntp listen-address` | Bind address (unsupported by sysntpd) | `service ntp listen-address 192.0.2.1` |
| `service ntp server` | NTP server hostname or address | `service ntp server ntp.aliyun.com` |
| `service router-advert interface <name> default-lifetime` | Default lifetime (seconds) | `service router-advert interface <name> default-lifetime 100` |
| `service router-advert interface <name> managed-flag` | Set the managed address flag | `service router-advert interface <name> managed-flag true` |
| `service router-advert interface <name> no-send-advert` | Do not send advertisements | `service router-advert interface <name> no-send-advert true` |
| `service router-advert interface <name> other-config-flag` | Set the other-config flag | `service router-advert interface <name> other-config-flag true` |
| `service router-advert interface <name> prefix` | Prefix to advertise | `service router-advert interface <name> prefix <value>` |
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
| `service snmp community <name> authorization` | ro \| rw | `service snmp community <name> authorization text` |
| `service snmp contact` | Administrator contact (sysContact) | `service snmp contact text` |
| `service snmp listen-address` | Bind address (default 0.0.0.0) | `service snmp listen-address 192.0.2.1` |
| `service snmp location` | System location (sysLocation) | `service snmp location text` |
| `service snmp port` | Listen port (default 161) | `service snmp port 8080` |
| `service sqm download` | Download bandwidth kbps | `service sqm download 100` |
| `service sqm interface` | WAN interface | `service sqm interface text` |
| `service sqm qdisc` | cake / fq_codel | `service sqm qdisc cake` |
| `service sqm upload` | Upload bandwidth kbps | `service sqm upload 100` |
| `service ssh access-control allow address` | Source prefix | `service ssh access-control allow address 192.0.2.1/24` |
| `service ssh access-control deny address` | Source prefix | `service ssh access-control deny address 192.0.2.1/24` |
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
| `system conntrack table-size` | Maximum conntrack entries | `system conntrack table-size 100` |
| `system conntrack timeout generic timeout` | Generic timeout | `system conntrack timeout generic timeout 100` |
| `system conntrack timeout icmp timeout` | ICMP timeout | `system conntrack timeout icmp timeout 100` |
| `system conntrack timeout tcp close` | Timeout in seconds | `system conntrack timeout tcp close 100` |
| `system conntrack timeout tcp close-wait` | Timeout in seconds | `system conntrack timeout tcp close-wait 100` |
| `system conntrack timeout tcp established` | Timeout in seconds | `system conntrack timeout tcp established 100` |
| `system conntrack timeout tcp fin-wait` | Timeout in seconds | `system conntrack timeout tcp fin-wait 100` |
| `system conntrack timeout tcp last-ack` | Timeout in seconds | `system conntrack timeout tcp last-ack 100` |
| `system conntrack timeout tcp syn-recv` | Timeout in seconds | `system conntrack timeout tcp syn-recv 100` |
| `system conntrack timeout tcp syn-sent` | Timeout in seconds | `system conntrack timeout tcp syn-sent 100` |
| `system conntrack timeout tcp time-wait` | Timeout in seconds | `system conntrack timeout tcp time-wait 100` |
| `system conntrack timeout udp other` | Other timeout | `system conntrack timeout udp other 100` |
| `system conntrack timeout udp stream` | Stream timeout | `system conntrack timeout udp stream 100` |
| `system dns` | System resolver for router itself (/etc/resolv.conf) | `system dns 192.0.2.1` |
| `system domain-search` | Domain search suffix (repeatable) | `system domain-search text` |
| `system flow-accounting interface` | Interface to monitor | `system flow-accounting interface text` |
| `system flow-accounting netflow server <name> port` | Collector port (default 2055) | `system flow-accounting netflow server <name> port 8080` |
| `system flow-accounting netflow server <name> version` | Export version (5 or 9) | `system flow-accounting netflow server <name> version 100` |
| `system flow-accounting sflow server <name> port` | Collector port (default 6343) | `system flow-accounting sflow server <name> port 8080` |
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
| `system sysctl parameter <name> value` | Value to set | `system sysctl parameter <name> value text` |
| `system syslog console facility` | Facility (all, daemon, kern, ...) | `system syslog console facility text` |
| `system syslog console level` | Severity (emerg..debug, all) | `system syslog console level text` |
| `system syslog global marker-interval` | Mark message interval (seconds) | `system syslog global marker-interval 100` |
| `system syslog global preserve-fqdn` | Include FQDN in remote messages | `system syslog global preserve-fqdn true` |
| `system syslog local facility` | Facility (all, daemon, kern, ...) | `system syslog local facility text` |
| `system syslog local level` | Severity (emerg..debug, all) | `system syslog local level text` |
| `system syslog remote <name> facility` | Facility (all, daemon, kern, ...) | `system syslog remote <name> facility text` |
| `system syslog remote <name> level` | Severity (emerg..debug, all) | `system syslog remote <name> level text` |
| `system syslog remote <name> port` | Destination port (default 514) | `system syslog remote <name> port 8080` |
| `system syslog remote <name> protocol` | udp \| tcp | `system syslog remote <name> protocol text` |
| `system timezone` | IANA timezone (e.g. Asia/Shanghai) | `system timezone Asia/Shanghai` |
| `system watchdog module` | Kernel watchdog module (e.g. softdog) | `system watchdog module text` |
| `system watchdog reboot-timeout` | Reboot timeout (seconds) | `system watchdog reboot-timeout 100` |
| `system watchdog shutdown-timeout` | Shutdown timeout (seconds) | `system watchdog shutdown-timeout 100` |
| `system watchdog timeout` | Runtime timeout (seconds) | `system watchdog timeout 100` |

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
| `vpn l2tp local-ip` | Local tunnel address | `vpn l2tp local-ip 192.0.2.1` |
| `vpn l2tp name-server` | DNS pushed to clients | `vpn l2tp name-server 192.0.2.1` |
| `vpn l2tp pool-end` | Client pool end | `vpn l2tp pool-end 192.0.2.1` |
| `vpn l2tp pool-start` | Client pool start | `vpn l2tp pool-start 192.0.2.1` |
| `vpn l2tp port` | UDP port (default 1701) | `vpn l2tp port 8080` |
| `vpn l2tp user <username> password` | Password | `vpn l2tp user <username> password text` |
| `vpn openconnect dpd` | Dead peer detection (s) | `vpn openconnect dpd 100` |
| `vpn openconnect max-clients` | Maximum clients | `vpn openconnect max-clients 100` |
| `vpn openconnect network` | Client address pool (a.b.c.d/nn) | `vpn openconnect network 192.0.2.1/24` |
| `vpn openconnect port` | TLS port (default 4443) | `vpn openconnect port 8080` |
| `vpn openconnect user <username> group` | Group | `vpn openconnect user <username> group text` |
| `vpn openconnect user <username> password` | Password | `vpn openconnect user <username> password text` |

## set vrf

| 命令 | 说明 | 示例 |
|---|---|---|
| `vrf name <vrf> table` | Routing table ID | `vrf name <vrf> table 100` |
