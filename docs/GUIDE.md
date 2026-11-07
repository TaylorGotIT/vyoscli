# vyoscli 操作与配置指南

本文是当前实现的操作手册，命令以 `schema/config-tree.json` 为准。
完整命令清单见 [COMMANDS.md](COMMANDS.md)；真机测试/已知问题见 [AUDIT.md](AUDIT.md)。

> 版本：0.1.0-r1  
> 目标：OpenWrt 23.05/24.10，Python 3.11  
> 入口：`vyoscli`（或 `/usr/bin/vyoscli`）

---

## 1. 登录与模式

```bash
root@OpenWrt:~# vyoscli
Welcome to vyoscli (a VyOS-style CLI for OpenWrt).

root@OpenWrt:~$            # 操作模式（op）
root@OpenWrt:~$ configure
root@OpenWrt#              # 配置模式（cfg）
root@OpenWrt# exit
root@OpenWrt:~$ exit       # 退出 CLI
```

- 操作模式：`show`、`ping`、`restart`、`monitor` 等，未识别命令会透传给 shell。
- 配置模式：`set/delete/edit/commit/rollback` 等。
- 配置模式下可用 `run <op命令>`，例如 `run show interfaces`。
- 提示符会显示当前 `edit` 路径，如 `root@OpenWrt# [interfaces ethernet eth0]`。

### Tab 与 `?`

```bash
root@OpenWrt# set 
Possible completions:
  container          Podman containers
  firewall           Firewall policy
  interfaces         Interface parameters
  nat                Network Address Translation
  policy             Routing policy
  protocols          Routing protocols
  service            System services
  system             System parameters
  vpn                VPN
```

- 多候选 Tab / `?` 输出 `Possible completions:` + 两列对齐。
- 唯一匹配直接补全；值占位符（`<x.x.x.x>`、`<1-65535>`）在下一行显示提示，不插入命令。
- `show` 输出过长时分页：空格下一页、`b` 上一页、`q` 退出。

---

## 2. 配置事务

```bash
root@OpenWrt# set system host-name r1
root@OpenWrt# compare
root@OpenWrt# commit
root@OpenWrt# show configuration commands
```

| 操作 | 命令 | 说明 |
|---|---|---|
| 写值 | `set <path> <value>` | 写入 candidate，不立即生效 |
| 删节点 | `delete <path>` | 删除子树/叶子 |
| 删列表项 | `delete <path> <value>` | 如 `delete system name-server 8.8.8.8` |
| 进入子树 | `edit <path>` / `next <path>` | 提示符显示路径 |
| 返回 | `up` | 上一层 |
| 查看 candidate | `show configuration` | 未提交内容 |
| 差异 | `compare` | running vs candidate |
| 提交 | `commit` | 生效 + 写 running.json + 快照 |
| 安全提交 | `commit confirmed 5` | 5 分钟不确认自动回滚 |
| 确认 | `commit confirm` | 取消定时器 |
| 丢弃 | `discard` | 丢弃 candidate |
| 回滚 | `rollback [ts]` | 回到历史快照 |
| 同步 | `sync` | 只重放漂移段 |
| 导出 | `show configuration json` | JSON |

### 远程操作防失联

改 SSH、WAN、防火墙、NAT 前：

```bash
root@OpenWrt# commit confirmed 5
# 另开一个 SSH 会话确认能登录、业务正常
root@OpenWrt# commit confirm
```

如果新配置导致失联，5 分钟后自动回滚到上一份 running。

### 漂移与开机对账

```bash
root@OpenWrt:~$ show system drift
No drift: committed UCI sections still match the running config.
```

有人手工改了 UCI，或配置被恢复，会显示 `changed/deleted <section>`。
`sync` 按 `applied.json` 只重放漂移的段落；开机时 `init.d/vyoscli` 也会后台执行一次。

### 快照

每次 `commit` 前保存到 `/etc/vyoscli/history/<ts>.json`，保留 20 个。

```bash
root@OpenWrt# rollback
root@OpenWrt# rollback 2026-01-01_12-00-00
```

---

## 3. 系统

```bash
set system host-name r1
set system timezone Asia/Shanghai
set system name-server 223.5.5.5
set system ntp ntp.aliyun.com
set system login user admin authentication plaintext-password 'StrongPass'
```

说明：

- `name-server` 写 dnsmasq 上游；`system dns` 写路由器自身 `/etc/resolv.conf`。
- 用户创建/删除依赖 `shadow-useradd`/`shadow-chpasswd`；缺失时提交会给出提示。
- `set system login user ... disable` 可禁用账户。

常用查看：

```bash
show system
show system uptime
show system cpu
show system memory
show system storage
show system login user
show system connections
show system drift
```

---

## 4. 接口

### 以太网 / MTU / TCP MSS / VIF

```bash
set interfaces ethernet eth0 address 192.168.1.1/24
set interfaces ethernet eth0 description LAN
set interfaces ethernet eth0 mtu 1400
set interfaces ethernet eth0 tcp-mss 1300
set interfaces ethernet eth0 vif 100 address 192.168.100.1/24
```

- `mtu` 同时写 UCI 和 `ip link`。
- 删除 `mtu` 只清 UCI，不现场改链路（避免管理口/WAN 失联）；重启/ifup 后恢复默认。
- `tcp-mss` 写 `/etc/nftables.d/20-vyos-mss.nft`，由 fw4 include 在 mangle 优先级生效。

### 桥 / dummy / loopback

```bash
set interfaces bridge br0 member eth1
set interfaces bridge br0 member eth2
set interfaces bridge br0 address 10.0.0.1/24

set interfaces dummy dum0 address 10.10.10.1/24
set interfaces loopback lo address 10.10.10.1/32
```

### WireGuard

```bash
set interfaces wireguard wg0 address 10.99.0.1/24
set interfaces wireguard wg0 private-key 'BASE64'
set interfaces wireguard wg0 listen-port 51820
set interfaces wireguard wg0 peer 'PEER_PUBLIC_KEY' endpoint 1.2.3.4:51820
set interfaces wireguard wg0 peer 'PEER_PUBLIC_KEY' allowed-ips 10.99.0.2/32
```

依赖 `kmod-wireguard`、`wireguard-tools`。运行时装包后 netifd 可能还没加载
proto，重启一次 network 即可。

### Tunnel / VXLAN

```bash
set interfaces tunnel tun0 encapsulation gre
set interfaces tunnel tun0 source-address 192.0.2.1
set interfaces tunnel tun0 remote 198.51.100.1
set interfaces tunnel tun0 address 10.0.0.1/30

set interfaces vxlan vx0 vni 42
set interfaces vxlan vx0 remote 198.51.100.2
```

---

## 5. 路由

### 静态路由

```bash
set protocols static route 10.0.0.0/8 next-hop 192.168.1.1
set protocols static table 110 route 0.0.0.0/0 next-hop 192.168.1.1
```

`show ip route static` 在 FRR 无静态路由时回退到内核 `proto static`，显示 `S>*`。

### BGP（VyOS 1.5 ASN 实例）

```bash
set protocols bgp 65000 parameters router-id 192.168.75.241
set protocols bgp 65000 timers holdtime 15
set protocols bgp 65000 timers keepalive 5

set protocols bgp 65000 address-family ipv4-unicast maximum-paths ibgp 4
set protocols bgp 65000 address-family ipv4-unicast redistribute connected

set protocols bgp 65000 neighbor 192.168.5.2 remote-as 65002
set protocols bgp 65000 neighbor 192.168.5.2 local-as 65001
set protocols bgp 65000 neighbor 192.168.5.2 address-family ipv4-unicast route-map export med100
set protocols bgp 65000 neighbor 192.168.5.2 address-family ipv4-unicast soft-reconfiguration inbound
set protocols bgp 65000 neighbor 192.168.5.2 bfd check-control-plane-failure

set protocols bfd peer 192.168.5.2 echo-mode
```

- 每次 BGP 配置提交会重启 FRR 以加载 `frr.conf`，邻居会短暂重建。
- `show ip bgp summary`、`show ip bgp neighbors <ip> received-routes` 查看路由。
- 多出口优先级用 route-map 设置 MED：`set metric 100/200`，数值小优先。

### OSPF / RIP / BFD

```bash
set protocols ospf router-id 192.168.1.1
set protocols ospf area 0 network 192.168.1.0/24

set protocols rip version 2
set protocols rip network 192.168.1.0/24

set protocols bfd interval 300
set protocols bfd min-rx 300
set protocols bfd multiplier 3
```

---

## 6. 策略路由

### route-map / community-list（VyOS 语法）

```bash
set policy community-list 80 rule 10 action permit
set policy community-list 80 rule 10 regex '65000:9939'

set policy route-map RM rule 100 action permit
set policy route-map RM rule 100 description to_hk
set policy route-map RM rule 100 match community community-list 80
set policy route-map RM rule 100 set ip-next-hop 10.10.57.1
set policy route-map RM rule 100 set local-preference 50
```

驱动会把 `rule` 归一化为 FRR 的 `permit/deny` 条目，并映射
`ip-next-hop -> next-hop`。

### 本地策略路由

```bash
set policy local-route rule 6600 source 192.168.1.1
set policy local-route rule 6600 set table 110
set protocols static table 110 route 0.0.0.0/0 next-hop 192.168.75.1
```

生成 `ip rule from 192.168.1.1 lookup 110` 和 table 110。

---

## 7. 防火墙与 NAT

```bash
# 过滤规则（inet vyos_fw, priority -10）
set firewall ipv4 input filter rule 100 action accept
set firewall ipv4 input filter rule 100 protocol tcp
set firewall ipv4 input filter rule 100 destination port 8080

# 组
set firewall group address-group AG address 203.0.113.0/24
set firewall group port-group PG port 8080
set firewall group interface-group IG interface eth0

# source NAT
set nat source rule 100 out-interface eth0
set nat source rule 100 translation address masquerade

# destination NAT
set nat destination rule 100 inbound-interface eth0
set nat destination rule 100 destination port 8080
set nat destination rule 100 translation address 10.0.0.10
```

- VyOS 规则表在 fw4 之前，`drop/reject` 可提前生效；`accept` 仍继续走 fw4 zone。
- NAT 使用独立 `inet vyos_nat` 表，先于 fw4 zone masquerade。
- 每次 apply 前会重建表，删除组/规则后不会残留旧 set。

---

## 8. DHCP / DNS

```bash
set service dhcp-server shared-network-name LAN interface lan
set service dhcp-server shared-network-name LAN subnet 192.168.1.0/24 default-router 192.168.1.1
set service dhcp-server shared-network-name LAN subnet 192.168.1.0/24 name-server 192.168.1.1
set service dhcp-server shared-network-name LAN subnet 192.168.1.0/24 lease 3600
set service dhcp-server shared-network-name LAN subnet 192.168.1.0/24 range R1 start 192.168.1.100
set service dhcp-server shared-network-name LAN subnet 192.168.1.0/24 range R1 stop 192.168.1.150
set service dhcp-server shared-network-name LAN subnet 192.168.1.0/24 static-mapping printer ip-address 192.168.1.50
set service dhcp-server shared-network-name LAN subnet 192.168.1.0/24 static-mapping printer mac-address aa:bb:cc:dd:ee:ff
```

- `interface` 填 **UCI 网络名**（`lan`/`wan`），不是 `br-lan`/`eth1`。
- 后端写 dnsmasq 的 `vyos_dhcp_*` 段；删除共享网络会清理对应段。

验证：

```bash
show dhcp server
show dhcp server pools
show dhcp server leases
show dhcp server static
```

完整隔离测试见 [DHCP-TEST.md](DHCP-TEST.md)。

DNS：

```bash
set service dnsmasq port 53
set service smartdns server aliyun ip 223.5.5.5
set service adguard enabled true
```

---

## 9. 容器（VyOS 结构）

```bash
# 虚拟网络
set container network vnet prefix 10.89.7.0/24
set container network vnet gateway 10.89.7.1

# host 网络
set container name c1 image docker.io/library/nginx:alpine
set container name c1 allow-host-networks

# 虚拟网络
set container name c2 image docker.io/library/busybox:latest
set container name c2 network vnet
set container name c2 volume conf source /config/c2/conf destination /app/conf
set container name c2 environment TZ value Asia/Shanghai
set container name c2 restart no
set container name c2 privileged
set container name c2 capability net-admin
set container name c2 device tun source /dev/net/tun destination /dev/net/tun
```

- `container network <name>` 不存在时驱动会自动 `podman network create`。
- 默认 netavark 需要 iptables/conntrack/addrtype 模块；缺模块时用
  `allow-host-networks` 或补齐依赖。
- 镜像拉取失败时先用 `add container image <img>` 或使用本地镜像。

查看：

```bash
show container
show container image
```

---

## 10. VPN

### L2TP

```bash
set vpn l2tp local-ip 10.99.9.1
set vpn l2tp pool-start 10.99.9.100
set vpn l2tp pool-end 10.99.9.150
set vpn l2tp user test password '***'
```

依赖 `xl2tpd`、`ppp-mod-pppol2tp`。

### IPsec

```bash
set vpn ipsec ike-group IKE1 proposal 10 encryption aes256
set vpn ipsec ike-group IKE1 proposal 10 hash sha256
set vpn ipsec esp-group ESP1 proposal 10 encryption aes256
set vpn ipsec esp-group ESP1 proposal 10 hash sha256
```

依赖 `strongswan-ipsec`、`strongswan-charon`、aes/sha2 插件。

### OpenVPN

```bash
set interfaces openvpn vtun9 mode server
set interfaces openvpn vtun9 proto udp
set interfaces openvpn vtun9 port 11999
set interfaces openvpn vtun9 dev tun
```

删除实例会清理 UCI、`/etc/openvpn/<name>.conf` 并重启服务。

---

## 11. 服务

```bash
set service ssh port 22
set service ssh password-auth true
set service ssh acl permit 192.168.75.0/24

set service ntp server pool.ntp.org
set service lldp interface eth0

set service mtr t1 target 1.1.1.1
set service mtr t1 count 10
set service mtr t1 interval 60
```

- `service ssh acl permit` 是 allow-list；添加前确保包含当前管理网段。
- `service mtr` 后台任务，日志在 `/etc/vyoscli/mtr/<name>.log`，
  `show service mtr` 查看最近跳数/丢失/中断。
- LLDP 依赖 `lldpd`。

---

## 12. 诊断

```bash
show interfaces
show interfaces ethernet eth0
show ip route
show ip route static
show ip bgp summary
show ip bgp neighbors 192.168.5.2 received-routes
show arp
show system connections
show system login user
show login
show service mtr
```

```bash
ping 1.1.1.1                  # 交互式长 ping，Ctrl+C 结束；非 TTY 只发 4 个
ping tcp 1.1.1.1 443
ping tcp ip 1.1.1.1 port 443
ping udp 1.1.1.1 53
```

`ping tcp/udp` 在 TTY 下每秒重复探测并输出 `[seq]`，Ctrl+C 打印
`sent/ok/failed` 汇总；非 TTY 单次探测，便于脚本。

---

## 13. 故障排查

| 现象 | 排查 |
|---|---|
| `set` 提示 `incomplete path` | 路径不在树中；用 Tab/`?` 看当前层候选 |
| commit 有 `... apply failed` | 缺依赖包或参数不合法；按提示装包/改值 |
| 配置改了没生效 | `compare`、`show system drift`；BGP 需等 FRR 重启 |
| 改 WAN 后失联 | 用 `commit confirmed`；console 下 `ifup wan` 或恢复 `/etc/config/network` |
| BGP 邻居 Active | 检查 `remote-as`、`local-as`、更新源、路由可达；`vtysh -c 'show bgp summary'` |
| DHCP 不分配 | `show dhcp server`、`netstat -lunp \| grep :67`；interface 必须是 UCI 名 |
| 容器网络失败 | 检查 netavark/iptables 模块；改用 `allow-host-networks` |
| Tab 无候选 | 确认层级/拼写；`?` 查看 `Possible completions:` |

日志：

```bash
show log
logread -f
vtysh -c 'show bgp summary'
```

---

## 14. 已知限制

- DHCP relay 的 `dhcp-fwd` 仍会退出，暂不可用。
- container 默认网络依赖较多内核模块；host 网络已验证。
- IPsec 仅验证 ike/esp 组与服务启动，site-to-site/证书未端到端。
- wireless 依赖硬件，未做端到端。
- commit 非原子：某段失败其余段仍执行并返回说明。
- BGP 提交会重启 FRR，邻居短暂重建。

更多测试记录与修复历史见 [AUDIT.md](AUDIT.md)。
