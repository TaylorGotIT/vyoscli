# Changelog

## 0.2.3 (2026-11-28)

### 新增

- BGP 恢复 VyOS 1.5 system-as 结构，支持 parameters、	imers、
  ddress-family（network、maximum-paths ibgp/ebgp、redistribute）、
  neighbor/peer-group 的 BFD、route-map import/export、soft-reconfiguration。
- protocols bfd peer <ip> interval transmit/receive/multiplier 毫秒级检测。
- eBGP ECMP：maximum-paths ebgp N 渲染为 FRR maximum-paths N +
  gp bestpath as-path multipath-relax。
- system ip multipath layer4-hashing：L3+L4 ECMP 哈希（IPv4/IPv6 sysctl）。
- route-map set extcommunity bandwidth 与
  parameters bestpath bandwidth default-weight-for-missing。
- 操作模式新增 iperf / iperf3 测速命令，支持客户端与服务端模式。
- 操作模式新增 	c 命令，透传 qdisc/class/filter 查询，便于网络测试。

## 0.2.2 (2026-11-18)

### 改进

- BGP 配置改为 **FRR 热加载**：使用 rr-reload.py --reload 应用
  frr.conf，路由/邻居/route-map 变更不再重启 FRR，已有邻居保持 Established，
  uptime 不重置。
- 仅当新增/删除 FRR daemon（如启用 ospfd/ripd/bfdd）时才后台重启。
- 新增依赖 rr-pythontools（提供 frr-reload.py）。
- 新增 service tph 透明网桥劫持：FDB 自动识别 WAN/LAN、同步网桥 MAC、
  二层防风暴与指定网段劫持；桥支持 mac、ddress dhcp、
  member interface ...，member 改为可重复列表。

### 打包

- 完整依赖包：dist/vyoscli_0.2.2-r1_all-full.ipk
  - SHA256：32BF3F2A68E0A797861C6995F66AC6EEAE285E840A64E3E0DB6AB4B1D544E8C6
- 最小依赖包：dist/vyoscli_0.2.2-r1_all-minimal.ipk
  - SHA256：A8B30A5EBAFF2368446BC2F68834466220D04D3DE4BE2FAFFBB118ECDAD77327

## 0.2.1 (2026-11-17)

### 新增

- show ipv6 route：支持 gp、connected、static、summary、
  kernel/orward、	able <id>，以及 show ipv6 route <prefix>；
  Tab 会列出子命令和 <h:h:h:h:h:h:h:h/x> 提示。
- 启动 banner、show version 和终端标题显示当前版本；yoscli --version 可直接查询。
- show interfaces ethernet <name> 拼错时给出 Did you mean 和可用接口列表。
- Tab 前缀无匹配时仍列出当前层候选，不再静默。

## 0.2.0 (2026-11-07)

### 新增

- **BGP 迁移到 VyOS 1.5 ASN 实例**：`protocols bgp <asn>`，支持
  `parameters router-id`、`timers`、`address-family`（maximum-paths ibgp、
  redistribute connected）、neighbor/peer-group 的 address-family、
  `local-as`、BFD、route-map import/export、soft-reconfiguration。
- **failover 路由**：`protocols failover route <prefix> next-hop <ip>`，
  支持 `check target/interface`、`metric`、`onlink`；后台每 5 秒探测，
  失败自动撤路由，多 next-hop 按 metric 选路。
- **container 改为 VyOS 结构**：`container name <name>` 与
  `container network <net>`，支持 `allow-host-networks`、`privileged`、
  `capability`、`device`、`volume`、`prefix/gateway/mtu`；网络不存在时
  自动创建。
- **Ethernet VIF 驱动**：`interfaces ethernet eth0 vif 100 ...` 创建
  VLAN link + UCI 接口，删除时清理。
- **route-map VyOS 语法**：`policy route-map <name> rule <n> action ...`
  `description`、`match community community-list`、`set ip-next-hop`。
- **Tab/`?` 默认值**：有默认值的叶子显示 `(default: X)`。
- **`show dependencies [feature]`**：按功能分组检查依赖，支持二进制回退，
  给出 `opkg install` 命令。

### 修复

- FRR 配置提交后不重载：现在会重启 FRR（后台），邻居变更生效。
- BGP 重启超时误报：改为非阻塞重启。
- mtu 删除不再现场改链路，避免管理口/WAN 失联。
- firewall 每次 apply 前重建 `inet vyos_fw`，删除组/规则不残留旧 set。
- dummy 删除同时删除链路。
- OpenVPN 删除清理 UCI/conf/进程。
- login user 删除支持无 `userdel` 环境（直接清理 passwd/shadow/group）。
- mtr `show service mtr` 恢复丢失的解析助手。
- DHCP：修复 `option:dns` 非法选项、命名 range 不生效、dummy 链路创建。
- 恢复 Tab/`?` 的 `Possible completions:` VyOS 风格。

### 文档

- README 整体重写。
- GUIDE 替换为当前可用的操作/配置手册，覆盖全部 service 示例。
- 新增 DHCP 测试模板、依赖策略、failover/容器/BGP 示例。

### 打包

- 版本：`0.2.0-r1`
- 完整依赖包：`dist/vyoscli_0.2.0-r1_all-full.ipk`
  - SHA256：`55BED5EAA9EED2EA9226C139C8090A7AC8F311E9C50CF69E5E29D63BAD78ECB8`
- 最小依赖包：`dist/vyoscli_0.2.0-r1_all-minimal.ipk`
  - SHA256：`716B61A4C23CCBB51C3E088920B47FFF4EB6C8541E89A9E8D03CB9EE39071D89`
- 真机安装验证：`vyoscli - 0.2.0-r1`，`No drift`，BGP 邻居正常。

## 0.1.0

- 初始版本：双模式 CLI、candidate/commit/rollback、UCI/nft/FRR 下发、
  基础接口/防火墙/NAT/DHCP/BGP/WireGuard/OpenVPN 等。
