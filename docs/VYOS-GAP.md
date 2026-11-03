# 与 VyOS 1.5（circinus）的差距分析

对比对象：VyOS 1.5.x LTS（circinus）官方配置指南
（<https://docs.vyos.io/en/1.5/configuration/>）与当前 vyoscli 配置树
（353 个节点、11 个顶层子树）。

状态图例：

- ✅ 已实现，且在真机（ImmortalWrt 23.05 / OpenWrt 23.05）验证过
- 🟡 部分实现，或只写了 JSON 尚未真正下发，或未做端到端验证
- ❌ 未实现

## 总览

| 顶层 | VyOS 1.5 内容 | vyoscli 现状 | 结论 |
|---|---|---|---|
| `interfaces` | 19 种接口 | 11 种（ethernet/bridge/wireguard/openvpn/tunnel/loopback/dummy/vxlan/wireless/lan/wan） | 🟡 缺 bonding、pppoe、macsec、geneve、vti、wwan 等 |
| `firewall` | ipv4/ipv6/bridge/zone/group/global-options/flowtable | ipv4/ipv6 input/forward/output filter rule + group（nft 表 `vyos_fw`）；zone/forwarding/rule 保留 | 🟡 方向规则与 group 已可用，缺 named rule-set/flowtable/bridge，global-options 仅存 JSON |
| `nat` | nat44 全量、nat64、nat66、cgnat | nat44 匹配/转换、静态 1:1、hairpin（nft `vyos_nat`） | 🟡 nat44 已完整，nat66/nat64/cgnat 未做 |
| `policy` | access-list/prefix-list/route/route-map/as-path/community/… | community-list、access-list、prefix-list、as-path-list；route-map 扩展了 prefix-list/as-path/metric/tag/next-hop/origin | 🟡 主体已补，缺 local-route/extcommunity/large-community |
| `protocols` | 静态、BGP、OSPF、ISIS、RIP、BFD、MPLS、SR、PIM… | static、bgp、ospf、rip、bfd、route-map | 🟡 BGP/OSPF/RIP/BFD 已可用，缺 ISIS/MPLS/SR/PIM |
| `service` | 22 类服务 | 10 类（含 OpenWrt 特有：sqm/adguard/smartdns/kcp） | 🟡 缺 NTP/DNS/HTTPS API/SNMP/LLDP/DHCP-relay 等 |
| `system` | 21 类 | 13 类（+syslog/conntrack/sysctl/watchdog） | 🟡 syslog/conntrack/sysctl/watchdog 已落地；缺 task-scheduler/console/ip/ipv6/updates 等 |
| `vpn` | IPsec、L2TP、SSTP、OpenConnect、PPTP、DMVPN | IPsec 子集 | 🟡 缺大部分 |
| `high-availability` | VRRP、sync-group、virtual-server | 无 | ❌ 完全缺失 |
| `load-balancing` | WAN 负载均衡、HAProxy | 无 | ❌ 完全缺失 |
| `pki` | CA/证书/DH/ACME、generate/import | 无 | ❌ 完全缺失 |
| `traffic-policy` | 11 种 qdisc + 接口 ingress/egress | 只有 `traffic-policy shaper`（5 节点） | 🟡 名称和结构都与 VyOS 的 `qos` 不同 |
| `container` | name/network/registry/health-check 等 | 9 节点极简 | 🟡 OpenWrt 默认无 podman，优先级低 |
| `vrf` | name + table + 接口绑定 | name + table | ✅ 基本够用 |

## 分项差距

### 1. firewall：方向规则与 group 已落地（P0 进行中）

VyOS 1.5 的防火墙是 **ipv4/ipv6 + 命名规则集 + group + zone** 的组合：

```
set firewall ipv4 input filter rule 10 action accept
set firewall ipv4 forward filter rule 20 inbound-interface name eth0
set firewall ipv4 forward filter rule 20 source address 192.168.0.0/16
set firewall ipv4 forward filter rule 20 state established enable
set firewall ipv4 name LAN-OUT rule 10 action drop
set firewall group address-group BLOCKED address 203.0.113.0/24
set firewall group port-group WEB port 80,443
set firewall global-options all-ping enable
set firewall zone LAN member interface eth1
set firewall zone LAN from WAN firewall name LAN-IN
```

我们目前只有 `firewall zone/forwarding/rule`，能力大致相当于 VyOS 1.2
时代的 zone 策略，**缺少按方向（input/forward/output/prerouting）组织规则、
named rule-set、group、global-options、flowtable、bridge 防火墙**。

需要补：

- `firewall ipv4|ipv6 input|forward|output filter rule <n>`：action、
  source/destination address/port、protocol、state、interface、mark、
  dscp、tcp-flags、log、disable、jump
- `firewall ipv4|ipv6 name <name> rule <n>`：命名规则集，供 zone/接口引用
- `firewall group`：address/network/port/interface/mac/domain group
- `firewall global-options`：all-ping、broadcast-ping、syn-cookies、
  state-policy、timeouts、log-martians
- `firewall flowtable`、`firewall bridge`
- zone 保留为便捷层，最终生成 `nft` 规则（OpenWrt 23.05 是 nftables/fw4）

### 2. nat：从"能用"到"完整"

VyOS 1.5 的 nat44 规则支持：

```
set nat source rule 100 outbound-interface name eth0
set nat source rule 100 source address 192.168.0.0/16
set nat source rule 100 destination address 10.0.0.0/8
set nat source rule 100 protocol tcp
set nat source rule 100 source port 1024-65535
set nat source rule 100 translation address masquerade
set nat destination rule 10 inbound-interface name eth0
set nat destination rule 10 destination port 8080
set nat destination rule 10 translation address 192.168.1.10
set nat destination rule 10 translation port 80
set nat destination rule 10 protocol tcp
```

已完成：source/destination 的地址、端口、协议匹配，`translation address`/`port`、
`log`、`disable`、`hairpin`、静态 1:1（不带 port 的 dnat），渲染到
`inet vyos_nat`（priority dstnat-10 / srcnat-10，先于 fw4 的 NAT）。
仍未做：exclude、nat66/nat64/cgnat。

### 3. policy：路由策略几乎空白

| VyOS 1.5 | 现状 | 说明 |
|---|---|---|
| `policy access-list` | ✅ | 标准/扩展 ACL，渲染到 FRR |
| `policy prefix-list` | ✅ | 前缀过滤（含 ge/le），渲染到 FRR |
| `policy as-path-list` | ✅ | AS 路径过滤，渲染到 FRR |
| `policy community-list` | 🟡 | 只有 regex |
| `policy extcommunity-list` | ❌ | |
| `policy large-community-list` | ❌ | |
| `policy route-map` | 🟡 | 现有 `protocols route-map`，match 支持 community/prefix-list/as-path/metric/tag，set 支持 community/local-preference/med/metric/tag/weight/next-hop/origin |
| `policy local-route` | ❌ | 本机流量策略路由 |
| `policy route` | ❌ | 我们叫 route-redirect，且只覆盖透明代理场景 |

### 4. protocols：只有 BGP/静态的骨架

VyOS 1.5 有 arp、babel、bfd、bgp、failover、igmp-proxy、isis、mpls、
multicast、segment-routing、traffic-engineering、openfabric、ospf、pim、
pim6、rip、rpki、static。

已有 `static route`、`bgp`、`ospf`（router-id/area network/interface cost/priority/
passive/default-information）、`rip`（version/network/default-information）、
`bfd`（interval/min-rx/multiplier）与 route-map。仍缺 OSPFv3、ISIS、MPLS/SR/PIM。

好消息是后端已经有 FRR（`render_frr_conf`），补 OSPF/BFD 主要是加命令树
+ 扩展现有 frr.conf 渲染，不需要新守护进程。

### 5. service：缺基础设施类服务

| VyOS 1.5 | 现状 | 备注 |
|---|---|---|
| `service ssh` | ✅ | dropbear |
| `service dhcp-server` | ✅ | dnsmasq |
| `service dns`（forwarding） | 🟡 | 用 dnsmasq/smartdns 代替，未按 VyOS 结构 |
| `service ntp` | ✅ | 写入 `system.ntp.server` 并重启 sysntpd |
| `service https`（API） | ❌ | 无 REST/GraphQL API |
| `service snmp` | ❌ | snmpd 可用 |
| `service lldp` | ✅ | UCI lldpd interface/description，已真机验证 |
| `service dhcp-relay` | ❌ | |
| `service router-advert` | ❌ | odhcpd/radvd 可用 |
| `service console-server` | ✅ | 已验证 per-device dropbear |
| `service task-scheduler` | 🟡 | 我们用 `service crontab` |
| `service monitoring` | ❌ | zabbix/telegraf/prometheus |
| `service eventhandler` | ❌ | |
| `service webproxy` | ❌ | |
| `service tftp-server` | ❌ | |
| `service pppoe-server` | ❌ | accel-ppp |
| `service conntrack-sync`/`config-sync` | ❌ | 配合 VRRP |
| OpenWrt 特有 | ✅ | sqm、adguard、smartdns、kcp（VyOS 没有） |

### 6. system：运维基础项不足

VyOS 1.5 有 acceleration、conntrack、console、flow-accounting、frr、host-name、
ip、ipv6、lcd、login、name-server、option、proxy、sflow、syslog、sysctl、
task-scheduler、time-zone、updates、watchdog、default-route。

我们已有：host-name、name-server、dns、timezone、domain-search、ntp、language、
hardware、login，以及新增的 `system syslog`（local/console/remote）、
`system conntrack`（table-size/timeout）、`system sysctl parameter`、
`system watchdog`。`default-route` 按 VyOS 1.5 文档就是
`protocols static route 0.0.0.0/0`（已支持）。仍缺 ip/ipv6 全局参数、updates、
console、task-scheduler（暂用 `service crontab`）。

### 7. vpn：只有 IPsec 子集

VyOS 1.5：ipsec（ike/esp/site-to-site/remote-access/vti）、l2tp、sstp、
openconnect、pptp、dmvpn、rsa-keys。

我们：ipsec ike-group/esp-group/site-to-site peer/tunnel/remote-access，
且证书模式、VTI、NAT 穿透参数不完整；L2TP/SSTP/OpenConnect 全缺。
OpenWrt 上 strongSwan、xl2tpd、openconnect、pptp 都有包，可按需补。

### 8. 完全缺失的顶层

| 顶层 | VyOS 1.5 能力 | OpenWrt 可行性 |
|---|---|---|
| `high-availability` | VRRP group/sync-group、virtual-server | keepalived 可用，建议做 VRRP |
| `load-balancing` | WAN 多线负载/故障切换、HAProxy | haproxy 可用；WAN 负载可用 mwan3 或 nft |
| `pki` | CA/证书/DH/ACME、generate/import | 可做证书存储（文件+JSON），ACME 可用 acme.sh |
| `container` | 完整 podman 编排 | OpenWrt 默认无 podman，**不建议作为近期目标** |

### 9. traffic-policy：结构差异

VyOS 1.5 是 `qos policy <type> <name>` + `qos interface <if> ingress|egress <policy>`，
支持 shaper/limiter/fq-codel/fair-queue/round-robin/drop-tail/priority-queue/
random-detect/rate-control/network-emulator/cake，以及 traffic-match-group。

我们只有 `traffic-policy shaper <name> interface/bandwidth/per-ip`（自研简化模型），
后端是 tc。建议改成 VyOS 的 `qos` 结构，至少支持 shaper/limiter/fq-codel/cake
和接口 ingress/egress 绑定。

## 优先级建议

### P0：不上会影响"当主路由用"

1. **firewall ipv4/ipv6 方向化规则 + group + global-options**
   —— 现在只能靠 zone 粗放控制，达不到 VyOS 的可用程度
2. **nat44 完整匹配/转换字段 + 静态 1:1 + hairpin**
3. **system syslog / conntrack / sysctl / watchdog / default-route**
4. **interfaces pppoe**（OpenWrt 主力场景是 PPPoE 拨号 WAN）
5. **policy access-list / prefix-list / as-path-list**，补齐 route-map 的 match/set

### P1：互联与运维

6. **protocols ospf/ospfv3、bfd、rip、static IPv6**（复用现有 FRR 渲染）
7. **service https（只做只读 API 也可）、ntp、snmp、lldp、dhcp-relay、router-advert**
8. **high-availability VRRP**（keepalived + conntrack-sync）
9. **pki**：证书/私钥入 JSON、供 IPsec/HTTPS/OpenVPN 引用
10. **vpn l2tp/sstp/openconnect**，补 IPsec 证书与 VTI
11. **qos**：按 VyOS 结构重做 traffic-policy（shaper/limiter/fq-codel/cake）

### P2：进阶/按需

12. nat66/nat64/cgnat
13. load-balancing（HAProxy + WAN 多线）
14. container 完整化（仅当目标设备能装 podman）
15. bonding、macsec、geneve、vti、l2tpv3、wwan、virtual-ethernet
16. MPLS/segment-routing/PIM/multicast、flow-accounting/sflow、webproxy、suricata

## 不建议照搬的部分

- `system updates`（VyOS 镜像升级机制）、`system lcd`、`system console` 串口控制台、
  `salt-minion`：与 OpenWrt 的 sysupgrade/配置模型冲突或没有对应硬件。
- `container` 作为近期目标：OpenWrt 默认软件源没有 podman。
- `service config-sync`：依赖 VyOS 的 config 同步协议，OpenWrt 无对应物。
- VyOS 的 `pki` 证书库格式可以简化：不必实现完整 certstore，
  先做到"证书/私钥存 JSON + 落盘到 /etc/vyoscli/pki/"即可被各服务引用。

## 落地方式（遵循当前架构）

每补一个功能组：

1. **命令树**：在 `config_tree.py` 增加节点（当前它是生成产物，见下方技术债）；
2. **下发**：在 `config.py` 增加 `_apply_<group>`，注册到 `_apply_steps()`，
   owner 名用于 `applied.json` 的漂移重放；
3. **测试**：`tests/test_paths.py` 加路径、`tests/test_apply.py` 断言生成的
   `uci`/`nft`/`tc` 命令、`tests/test_schema.py` 自动覆盖新叶子；
4. **文档**：`python3 scripts/gen-command-reference.py` 重新生成
   `docs/COMMANDS.md`；
5. **真机**：在测试路由器上 commit/回滚验证，记录到 `docs/AUDIT.md`。

## 技术债提醒

`config_tree.py` 目前是"从旧手写树一次性生成"的 JSON 数据，
生成脚本依赖已删除的旧树（`dist/gen_config_tree.py` 读的是基线 dump）。
也就是说，**它现在是事实上的手写源**，"不要手改"的注释已经名不副实。
建议下一步二选一：

- 把 `config_tree.py` 正式当源文件维护，删掉误导性注释；
- 或引入真正的 authored schema（YAML/JSON），再由它生成 `config_tree.py`，
  并把 `dist/gen_config_tree.py` 重写成"schema → tree"。

在补功能前先定这件事，否则每加一个命令都要同时维护两套结构。
