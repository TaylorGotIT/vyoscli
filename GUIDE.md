# vyoscli 配置指南

类 VyOS 的 OpenWrt CLI。目录结构对齐 [VyOS 1.5 官方文档](https://docs.vyos.io/en/1.5/configuration/index.html)。

## 目录

- [入门](#入门)
- [System](#system)
- [Interfaces](#interfaces)
- [Protocols](#protocols)
- [VPN](#vpn)
- [Service](#service)
- [Firewall](#firewall)
- [NAT](#nat)
- [VPN](#vpn)
- [Container](#container)
- [Traffic Policy](#traffic-policy)
- [运维](#运维)

---

## 功能概览


类 VyOS 的 OpenWrt CLI，opkg 包 `vyoscli`。

## 交互模型

| 特性 | 说明 |
|---|---|
| 双模式 | op `root@host:~$` / config `root@host#` |
| candidate 配置 | 改配置不立即生效，存 candidate.json |
| commit | candidate → running，自动打快照（保留 20 个） |
| commit confirmed N | 生效但挂 N 分钟定时器，超时自动回滚 |
| commit confirm | 取消挂起的定时器 |
| rollback [ts] | 手动回滚到任意历史快照 |
| discard | 丢弃未提交修改 |
| Tab 补全 | 两列对齐：命令名 + help 描述 |

## op 模式

| 命令 | 作用 |
|---|---|
| `configure` | 进入配置模式 |
| `exit` / `quit` | 退出 CLI |
| `show version` | 版本/内核/架构/硬件资产卡 |
| `show interface` | 接口 IP 摘要（多 IP 换行） |
| `show configuration` | running 配置树形缩进 |
| `show configuration commands` | running 配置为 `set ...` 脚本 |
| `show configuration json` | running 配置为 JSON |
| `show system` | uptime/cpu/memory/storage/processes/kernel-messages/login |
| `show ip route` / `static` / `connected` / `summary` | 路由表 |
| `show container` | podman 容器列表 |
| `show container image` | podman 镜像列表 |
| `show dhcp lease` | dnsmasq DHCP 租约 |
| `show smartdns` | smartdns 状态 |
| `add container image <name>` | podman pull |
| `delete container image <name>` | podman rmi |

## 配置树

```
set system
  host-name <text>
  timezone <IANA tz>                e.g. Asia/Shanghai
  ntp server <host>
  language <locale>
  name-server <ipv4>                dnsmasq 上游
  dns <ipv4>                        路由器自身 resolver
  hardware vendor/model/serial

set interfaces ethernet <ifname>
  address <ipv4/pfx>                (可重复)
  description <text>
  role <lan|wan>

set interfaces wireless <ifname>
  mode <ap|sta>
  ssid <text>
  channel <num>
  security <wpa2|wpa3|none>
  key <text>

set interfaces bridge br0
  member <ifname>
  address <ipv4/pfx>

set interfaces dummy dum0
  address <ipv4/pfx>

set interfaces tunnel tun0
  mode <gre|ipip>
  local-ip <ipv4>
  remote-ip <ipv4>
  address <ipv4/pfx>

set interfaces vxlan vxlan0
  vni <num>
  remote <ipv4>

set interfaces wireguard wg0
  address <ipv4/pfx>
  private-key <key>
  listen-port <port>
  peer <pubkey>
    allowed-ips <cidr>
    endpoint <ip:port>

set interfaces openvpn vtun0
  mode <tun>
  config-file <path>

set protocols static route <prefix>
  next-hop <ipv4>

set protocols bgp
  local-as <asn>
  router-id <ipv4>
  network <cidr>                    (可重复)
  neighbor <ipv4>
    remote-as <asn>
    description <text>
    route-map-in <name>
    route-map-out <name>

set protocols route-map <name> permit <num>
  set local-preference <n>
  set med <n>
  set community <asn:nn>
  set next-hop <ipv4>

set service ssh
  port <port>
  root-login <true|false>

set service dhcp <ifname>
  start <ipv4>
  end <ipv4>
  lease <time>
  gateway <ipv4>
  dns <ipv4>                        (可重复)

set service smartdns
  enabled <true|false>
  port <port>
  listen-address <ipv4>
  forbid-aaaa <true|false>
  server <name> ip <ipv4>
  domain-rules-file <path>

set service adguard
  enabled <true|false>
  port <port>
  listen-address <ipv4>
  web-port <port>

set service dnsmasq
  port <port>
  listen-address <ipv4>

set service crontab <name>
  schedule "<cron>"
  command <path>

set firewall zone <name>
  network <net>
  input/output/forward ACCEPT|DROP|REJECT

set firewall forwarding <name>
  src <zone>
  dest <zone>

set firewall rule <num>
  name <text>
  src <zone>
  dest-port <port>
  target ACCEPT|DROP|REJECT

set nat source rule <num>
  out-interface <if>
  translation masquerade

set nat destination rule <num>
  in-interface <if>
  port <port>
  to <internal-ipv4>

set container <name>
  image <image>
  network <net>
  port <host:container>             (可重复)
  volume <host:container>           (可重复)
  restart <always|on-failure|no>
  command <text>
  environment <KEY> value <text>
```

## 底层下发

| 配置 | 下发方式 | reload |
|---|---|---|
| interfaces ethernet/bridge/dummy | UCI network.* | netifd reload |
| interfaces wireless | UCI wireless.vyos_* | wifi reload |
| interfaces tunnel/vxlan | UCI interface.vyos_* | netifd reload |
| interfaces wireguard | UCI network/network.wg0 | wg-quick up |
| interfaces openvpn | /etc/openvpn/*.conf | openvpn init restart |
| system host-name/timezone/ntp | UCI system.* | sysntpd restart |
| system name-server | UCI dhcp.@dnsmasq[0].server | dnsmasq reload |
| system dns | /tmp/resolv.conf.d/resolv.conf.head | - |
| protocols static route | UCI network.vyos_route_* | netifd reload |
| protocols bgp | UCI frr.vyos_bgp_* + frr.conf 标记块 | restart（核心变）/ vtysh 热加载（route-map） |
| service ssh | UCI dropbear.* | dropbear restart |
| service dhcp | UCI dhcp.vyos_* | dnsmasq reload |
| service dnsmasq | UCI dhcp.@dnsmasq[0].port/listenaddress | dnsmasq restart |
| service smartdns | UCI smartdns.vyos_* | smartdns restart |
| service adguard | UCI adguardhome.main | adguardhome restart |
| service crontab | /etc/crontabs/root（标记块） | cron restart |
| firewall | UCI firewall.vyos_* | firewall reload |
| nat | UCI firewall.vyos_nat_* | firewall reload |
| container | podman rm -f / podman run | - |

## DNS 端口冲突检测

commit 前自动检测：
- dnsmasq / smartdns / adguard 都纳入 candidates
- 按 IP:端口粒度判定（`ss -tulnp`）
- 0.0.0.0 通配监听会和任何同端口冲突
- 冲突直接拒绝 commit，running 回滚到旧值

## 按需安装（commit 时才 opkg install）

| 包 | 触发条件 |
|---|---|
| smartdns | set service smartdns enabled true |
| adguardhome | set service adguard enabled true |
| podman / podman-plugins | set container ... |
| frr | set protocols bgp local-as |
| kmod-wireguard / wireguard-tools | set interfaces wireguard |
| openvpn-openssl | set interfaces openvpn |

硬依赖仅 python3 + python3-readline + ip-full（~6 MB）。

## 目录布局

```
/etc/vyoscli/
├── running.json         当前运行配置
├── candidate.json       未提交修改
├── rollback.conf        挂起的回滚定时器
├── history/             commit 快照（保留 20 个）
├── scripts/             用户脚本（cron 调用）
├── lists/               域名列表等数据文件
└── adguard/             AdGuardHome 持久化配置
```

迁移：`tar czf /tmp/vyoscli.tgz -C /etc vyoscli/`，新设备解包后 commit。

---

## 入门

```
root@OpenWrt:~$ configure
root@OpenWrt# set ...
root@OpenWrt# commit
root@OpenWrt# exit
```

远程改 SSH/firewall/VPN 必用：

```
root@OpenWrt# commit confirmed 3
root@OpenWrt:~$ commit confirm
```

---

## System

### Hostname

```
set system host-name router-gz
commit
```

### Timezone / NTP

```
set system timezone Asia/Shanghai
set system ntp server ntp.aliyun.com
commit
```

### DNS

```
# 路由器自身 resolver
set system dns 223.5.5.5

# dnsmasq 上游（客户端用）
set system name-server 223.5.5.5
commit
```

### Login User

本地用户管理。

```
set system login user admin full-name "Administrator"
set system login user admin authentication plaintext-password mypass123
commit
```

SSH 公钥：

```
set system login user admin authentication public-keys laptop key "AAAAB3NzaC1yc2E..."
set system login user admin authentication public-keys laptop type ssh-rsa
commit
```

禁用账号：

```
set system login user admin disable
commit
```
### Hardware asset

```
set system hardware vendor "Custom"
set system hardware model "x86-2L"
set system hardware serial "E1X16225005023060077"
commit
```

---

## Interfaces

### Ethernet

```
set interfaces ethernet eth0 description WAN
set interfaces ethernet eth0 address dhcp

set interfaces ethernet eth1 description LAN
set interfaces ethernet eth1 address 192.168.1.1/24
set interfaces ethernet eth1 address 192.168.2.1/24
commit
```

### Interface role

```
set interfaces ethernet eth0 role wan
set interfaces ethernet eth1 role lan
commit
```

### Wireless

```
set interfaces wireless wlan0 mode ap
set interfaces wireless wlan0 ssid "MyWiFi"
set interfaces wireless wlan0 security wpa2
set interfaces wireless wlan0 key "password123"
commit
```

### Bridge
### Bridge

#### 普通桥接

```
set interfaces bridge br0 member eth1
set interfaces bridge br0 address 192.168.1.1/24
commit
```

#### 透明桥接（bump-in-the-wire）

串接在 PC 和网关之间，设备像一根透明网线，插上即用。

```
set interfaces bridge br100 mac-rebinding
set interfaces bridge br100 mac cc:d3:9d:92:30:bd
set interfaces bridge br100 member interface eth0
set interfaces bridge br100 member interface eth1
set interfaces bridge br100 address 192.168.1.2/24
commit
```

| 配置 | 说明 |
|---|---|
| mac-rebinding | 启用透明桥接模式 |
| mac | 桥接口 MAC 地址（用于劫持流量） |
| member interface eth0 | WAN 侧（接网关） |
| member interface eth1 | LAN 侧（接 PC） |
| address | 设备管理 IP（和网关同网段） |

##### 工作原理

1. **网关发现**：自动探测 WAN 侧网关 MAC/IP
2. **二层劫持**：PC 发往网关的包，目的 MAC 改成 br100 的 MAC，交给本机处理
3. **流量伪装**：本机发出去的包，源 MAC 改回 PC 的 MAC，网关以为是 PC 直接发的

##### 拓扑

```
PC ---- eth1 [OpenWrt br100] eth0 ---- 网关 ---- 互联网
```

PC 和网关都以为对方在直接通信，不知道中间串了台 OpenWrt。

##### bypass 保护

设备断电/故障时，eth0/eth1 物理直连，流量自动透传，不影响客户上网。
### Dummy

##### Trunk 多 VLAN

如果上行是 trunk 多 VLAN，开启 VLAN 感知：

```
set interfaces bridge br100 vlan-aware true
set interfaces bridge br100 vlan 100 untagged eth1
set interfaces bridge br100 vlan 100 tagged eth0
set interfaces bridge br100 vlan 200 untagged eth1
set interfaces bridge br100 vlan 200 tagged eth0
commit
```

| 配置 | 说明 |
|---|---|
| vlan-aware | 开启 VLAN 过滤 |
| untagged eth1 | eth1 接 PC，无标签 |
| tagged eth0 | eth0 接网关，trunk 带标签 |

```
set interfaces dummy dum0 address 10.255.0.1/32
commit
```

### Tunnel (GRE / IPIP)

```
set interfaces tunnel tun0 mode gre
set interfaces tunnel tun0 local-ip 1.1.1.1
set interfaces tunnel tun0 remote-ip 2.2.2.2
set interfaces tunnel tun0 address 10.0.0.1/30
commit
```

### VXLAN

```
set interfaces vxlan vxlan0 vni 100
set interfaces vxlan vxlan0 remote 239.1.1.1
set interfaces vxlan vxlan0 address 192.168.100.1/24
commit
```

---

## Protocols

### Static route

```
# 普通路由
set protocols static route 0.0.0.0/0 next-hop 192.168.1.1

# 黑洞（静默丢弃）
set protocols static route 192.168.99.0/24 blackhole

# 拒绝（ICMP unreachable）
set protocols static route 10.99.0.0/16 reject

commit
```

查看：show ip route

### BGP

```
set protocols bgp local-as 65001
set protocols bgp router-id 192.168.1.1

set protocols bgp neighbor 10.0.0.2 remote-as 65002
set protocols bgp neighbor 10.0.0.2 description "ISP-A"

set protocols bgp network 192.168.1.0/24
commit
```


#### Community-list + Route-map

按 BGP community 分流到不同下一跳：

```
# community-list
set policy community-list 80 rule 10 action permit
set policy community-list 80 rule 10 description to_hk
set policy community-list 80 rule 10 regex 65000:9939

# route-map match community
set protocols route-map bgp-from-RSVR permit 100 description to_hk
set protocols route-map bgp-from-RSVR permit 100 match community community-list 80
set protocols route-map bgp-from-RSVR permit 100 set ip-next-hop 10.70.124.121
set protocols route-map bgp-from-RSVR permit 100 set local-preference 200

# peer-group
set protocols bgp peer-group RSVR remote-as 65000
set protocols bgp peer-group RSVR update-source 10.20.182.144
set protocols bgp peer-group RSVR route-map-import bgp-from-RSVR
set protocols bgp peer-group RSVR soft-reconfiguration inbound

# neighbor 加入 peer-group
set protocols bgp neighbor 10.10.99.160 peer-group RSVR
commit
```
---

## Service

### SSH

```
set service ssh port 22
set service ssh root-login true
commit

# 关闭
set service ssh disable
commit

# 恢复
delete service ssh disable
commit
```

### DHCP

```
set service dhcp br0 start 192.168.1.100
set service dhcp br0 end 192.168.1.200
set service dhcp br0 lease 12h
set service dhcp br0 gateway 192.168.1.1
set service dhcp br0 dns 192.168.1.1
commit
```

查看租约：`show dhcp lease`

##### MAC-IP 绑定

```
set service dhcp br0 static 00:11:22:33:44:55 ip 192.168.1.10
set service dhcp br0 static 66:77:88:99:AA:BB ip 192.168.1.11
commit
```

### DNS Forwarding

基于 dnsmasq 的 DNS 转发器。

#### 上游 DNS

```
# 全局上游
set service dnsmasq name-server 223.5.5.5
set service dnsmasq name-server 8.8.8.8

# 按域名转发（split-horizon）
set service dnsmasq domain internal.corp name-server 10.0.0.1
commit
```

#### 监听地址和端口

```
set service dnsmasq listen-address 192.168.1.1
set service dnsmasq port 53
commit
```

#### 允许查询的客户端

```
set service dnsmasq allow-from 192.168.1.0/24
commit
```

#### 缓存

```
set service dnsmasq cache-size 10000
set service dnsmasq negative-ttl 3600
commit
```

#### DNSSEC

```
set service dnsmasq dnssec validate
# 可选：off | process-no-validate | process | log-fail | validate
commit
```

### SmartDNS

高性能 DNS 转发，支持按域名测速选最快上游。

```
set service smartdns enabled true
set service smartdns port 5333
set service smartdns listen-address 127.0.0.1
set service smartdns forbid-aaaa true

set service smartdns server aliyun ip 223.5.5.5
set service smartdns server google ip 8.8.8.8

# 域名列表文件
set service smartdns domain-rules-file /etc/vyoscli/lists/domains.txt
commit
```

### AdGuardHome

带广告过滤的 DNS。

```
set service adguard enabled true
set service adguard port 53
set service adguard listen-address 127.0.0.1
set service adguard web-port 3000
commit
```

Web UI：`http://<router-ip>:3000`

### DNS 冲突保护

commit 时自动检测 dnsmasq/smartdns/adguard 的 IP:端口冲突，冲突直接拒掉。

### Console Server

串口控制台服务器，远程管理多台设备。基于 conserver + dropbear 多实例。

#### USB 驱动

```
opkg update
opkg list-installed *usb-serial*
opkg list *usb-serial*

# 按芯片装驱动
opkg install kmod-usb-serial-pl2303    # Prolific PL2303
opkg install kmod-usb-serial-ftdi      # FTDI FT232/FT4232
```

查看设备：

```
show hardware usb
lsusb
ls -lsh /dev/ttyUSB*
```

#### 配置

```
set service console-server device usb0 description "core-sw-1"
set service console-server device usb0 speed 115200
set service console-server device usb0 data-bits 8
set service console-server device usb0 parity none
set service console-server device usb0 stop-bits 1
set service console-server device usb0 ssh-port 2201
commit
```

#### commit 后

1. 自动 `opkg install conserver`
2. 写 `/etc/conserver/conserver.cf`
3. 起 conserver 服务
4. 每个串口起一个 dropbear 实例：
   ```
   /usr/sbin/dropbear -j -k -r /etc/dropbear/dropbear_rsa_host_key \
     -c 'console usb0' -P /var/run/vyoscli-console-usb0.pid -p 2201
   ```

#### 远程访问

```
ssh root@<router-ip> -p 2201
```

#### 快捷键

- `Ctrl+E c ?` 帮助
- `Ctrl+E c .` 断开
- `Ctrl+E c f` 强制接管
- `Ctrl+E c b` 广播消息

#### 强制下线占用会话

```
show console-server ports
fuser -k /dev/ttyUSB0
```

#### 本地串口工具

```
# picocom
opkg install picocom
picocom -b 115200 /dev/ttyUSB0    # Ctrl+A Ctrl+X 退出

# screen
opkg install screen
screen -S console /dev/ttyUSB0 115200   # Ctrl+A D 退出
screen -ls
screen -r <pid>
```
### Crontab

```
set service crontab update-domains schedule "0 3 * * *"
set service crontab update-domains command /etc/vyoscli/scripts/update-domains.sh
commit
```


### SQM

智能队列管理，解决 bufferbloat，游戏低延迟。

```
set service sqm interface eth0
set service sqm download 100000
set service sqm upload 10000
set service sqm qdisc cake
commit
```

| qdisc | 说明 |
|---|---|
| cake | 现代 AQM，自动公平分配带宽（推荐） |
| fq_codel | 经典队列管理 |
### TCP Accelerate

BBR / Hybla 拥塞控制 + fq_codel 队列，优化高丢包跨境链路。

```
set service tcp-accelerate congestion-control bbr
set service tcp-accelerate fq-codel true
commit
```

| congestion-control | 适用场景 |
|---|---|
| bbr | 高丢包跨境链路（推荐） |
| hybla | 卫星链路 |
| cubic | 默认 |

### KCP Accelerate

kcptun UDP 隧道，配合 OpenVPN over TCP 使用，高丢包链路加速。

#### CE 端（客户端）

```
set service kcp acc1 mode c
set service kcp acc1 local-ip 192.168.144.201
set service kcp acc1 local-port 22222
set service kcp acc1 remote-ip 192.168.144.202
set service kcp acc1 remote-port 9991
set service kcp acc1 kcp-mode fast3
commit
```

#### PE 端（服务端）

```
set service kcp acc1 mode s
set service kcp acc1 local-ip 192.168.144.202
set service kcp acc1 local-port 9991
set service kcp acc1 remote-ip 192.168.144.202
set service kcp acc1 remote-port 10064
set service kcp acc1 kcp-mode fast3
commit
```

| kcp-mode | 效果 |
|---|---|
| fast2 | 10% 重发，延迟低 |
| fast3 | 20% 重发，丢包补偿（推荐） |
| normal | 标准模式 |
## VPN

### IPsec Site-to-Site

基于 strongswan 的站点间 VPN。

#### Phase 1 (IKE)

```
set vpn ipsec ike-group IKE lifetime 28800
set vpn ipsec ike-group IKE proposal 10 encryption aes256
set vpn ipsec ike-group IKE proposal 10 hash sha256
set vpn ipsec ike-group IKE proposal 10 dh-group 14
```

#### Phase 2 (ESP)

```
set vpn ipsec esp-group ESP lifetime 3600
set vpn ipsec esp-group ESP proposal 10 encryption aes256
set vpn ipsec esp-group ESP proposal 10 hash sha256
```

#### Peer

```
set vpn ipsec site-to-site peer 10.0.2.2 local-address 10.0.1.2
set vpn ipsec site-to-site peer 10.0.2.2 remote-address 10.0.2.2
set vpn ipsec site-to-site peer 10.0.2.2 local-id 10.0.1.2
set vpn ipsec site-to-site peer 10.0.2.2 remote-id 10.0.2.2
set vpn ipsec site-to-site peer 10.0.2.2 secret mysecret
set vpn ipsec site-to-site peer 10.0.2.2 ike-group IKE
set vpn ipsec site-to-site peer 10.0.2.2 esp-group ESP
set vpn ipsec site-to-site peer 10.0.2.2 tunnel 0 local-prefix 192.168.1.0/24
set vpn ipsec site-to-site peer 10.0.2.2 tunnel 0 remote-prefix 192.168.2.0/24
commit
```

#### commit 后

1. 自动 `opkg install strongswan-minimal`
2. 写 `/etc/ipsec.conf` + `/etc/ipsec.secrets`
3. `/etc/init.d/ipsec restart`

#### 查看

```
show ipsec sa
```
---

## Firewall

### Zone

```
set firewall zone lan network br0
set firewall zone lan input ACCEPT
set firewall zone lan output ACCEPT
set firewall zone lan forward ACCEPT

set firewall zone wan network eth0
set firewall zone wan input DROP
set firewall zone wan output ACCEPT
set firewall zone wan forward DROP
commit
```

### Forwarding

```
set firewall forwarding lan-wan src lan
set firewall forwarding lan-wan dest wan
commit
```

### Rule

```
set firewall rule 10 name "allow-ssh"
set firewall rule 10 src wan
set firewall rule 10 dest-port 22
set firewall rule 10 target ACCEPT
commit
```

---

## NAT

### Source NAT

```
set nat source rule 10 out-interface wan
set nat source rule 10 translation masquerade
commit
```

### Destination NAT

```
set nat destination rule 20 in-interface wan
set nat destination rule 20 port 80
set nat destination rule 20 to 192.168.1.10
commit
```

---

### WireGuard

```
set interfaces wireguard wg0 address 10.0.10.1/24
set interfaces wireguard wg0 private-key "xxxxbase64xxxx"
set interfaces wireguard wg0 listen-port 51820

set interfaces wireguard wg0 peer abcpublickey allowed-ips 10.0.10.2/32
set interfaces wireguard wg0 peer abcpublickey endpoint 1.2.3.4:51820
commit
```

### OpenVPN

```
set interfaces openvpn vtun0 mode tun
set interfaces openvpn vtun0 config-file /etc/vyoscli/openvpn/client.ovpn
commit
```

---

## Container

基于 Podman 的容器引擎。

### 镜像 Image

```
# 指定镜像
set container nginx image nginx:alpine

# 指定仓库 registry
set container nginx image quay.io/nginx:alpine
commit
```

### 网络 Network

```
# 加入已有 podman 网络
set container nginx network podman

# 静态 IP
set container nginx network podman address 10.89.0.10
commit
```

### 端口映射 Port

```
# 主机 8080 -> 容器 80
set container nginx port 8080:80
commit
```

### 卷挂载 Volume

```
# 配置文件挂载（只读）
set container nginx volume /etc/nginx/conf.d:/etc/nginx/conf.d:ro
commit
```

### 环境变量 Environment

```
set container mysql environment MYSQL_ROOT_PASSWORD value 'secret'
set container mysql environment MYSQL_DATABASE value 'appdb'
commit
```

### 重启策略 Restart

```
set container nginx restart always
# 可选：always | on-failure | no
commit
```

### 资源限制 Resource

```
set container nginx memory 256
set container nginx cpu-quota 0.5
commit
```

### 禁用 Disable

```
set container nginx disable
commit
```

### 操作命令 Operations

```
show container                       # 运行中容器
show container image                 # 本地镜像
add container image nginx:alpine    # pull
delete container image nginx:alpine # rmi
restart container nginx             # 重启
```

### 完整示例 Example

```
set container mysql image mysql:8.0
set container mysql network podman
set container mysql environment MYSQL_ROOT_PASSWORD value 'rootpwd'
set container mysql environment MYSQL_DATABASE value 'appdb'
set container mysql restart always

set container nginx image nginx:alpine
set container nginx network podman
set container nginx port 8080:80
set container nginx restart always
commit
```

---

## Traffic Policy

route-map：

```
set protocols route-map FROM-ISP permit 10 set local-preference 200
set protocols route-map FROM-ISP permit 10 set med 50
set protocols route-map FROM-ISP permit 10 set community 65001:100
set protocols bgp neighbor 10.0.0.2 route-map-in FROM-ISP
commit
```

---

## 运维

```
show version
show interface
show configuration
show configuration commands
show system
show ip route
show container
show dhcp lease

restart service ssh
reload service firewall
```

备份：

```
tar czf /tmp/vyoscli.tgz -C /etc vyoscli/
```
