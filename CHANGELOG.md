# Changelog

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
