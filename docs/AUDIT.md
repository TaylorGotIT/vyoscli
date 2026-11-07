# 项目整理与代码审查报告

> 日期：2026-11-04
> 审查对象：`package/vyoscli`（v0.1.0，71 commits）
> 验证环境：Windows 10 / Python 3.10（本地单测）+ ImmortalWrt 23.05.2 x86_64 / Python 3.11.7（真机只读验证）

---

## 1. 项目现状

一个用 Python 实现的 VyOS 风格 CLI，作为 OpenWrt 的 opkg 包发布。核心模型是
**op / config 双模式 + candidate → commit → running 三段式**，配置以 JSON 落盘，
commit 时翻译成 UCI / 原生命令下发。

| 模块 | 行数 | 职责 |
|---|---:|---|
| `config.py` | 2136 | 配置库、事务、40+ 个 `_apply_*` 下发函数、渲染 |
| `commands.py` | 1124 | 命令树定义（op 命令 + `set/delete/edit` 三份配置树） |
| `cli.py` | 384 | REPL、补全、命令分发、prompt |
| `op_show.py` | 350 | `show *` 系列实现与依赖检查 |
| `tree.py` | 205 | 命令树节点、前缀匹配、动态节点 |
| `__main__.py` / `__init__.py` | 41 | 入口、回滚定时器子进程 |

磁盘布局：`/etc/vyoscli/{running,candidate}.json`、`history/`（20 个快照）、
`rollback.conf`（挂起的 confirmed-commit 定时器）。

真机实测开销（ImmortalWrt 23.05.2，x86_64）：

```
import vyoscli.cli          ≈ 0.07 s
完整 CLI（建树 + 读配置）    ≈ 13 MB RSS
```

对 128 MB 内存的路由器可以接受，对 64 MB / 16 MB flash 的设备偏重（见 §5 打包建议）。

---

## 2. 本次整理做了什么

### 2.1 仓库结构

| 变更 | 说明 |
|---|---|
| `GUIDE.md` → `docs/GUIDE.md`，`REQUIRED_PACKAGES.md` → `docs/DEPENDENCIES.md` | 文档集中到 `docs/` |
| 新增 `tests/`（7 个文件、116 个用例） | 替代根目录 15 个 `smoke_test*.py`（已删除） |
| 新增 `.gitignore` | 忽略 `__pycache__`、`*.ipk`、`.audit/` 等 |
| `git rm --cached package/vyoscli.zip` | 陈旧构建产物，已从仓库移除 |
| `Makefile` 安装改用 `$(wildcard .../*.py)` | 以后加模块不用再改 Makefile |
| `files/etc/init.d/vyoscli` 改为 `boot()` | 原来 `USE_PROCD` 却没有 command，实例是空壳 |

### 2.2 已修复的缺陷（均有测试覆盖）

| # | 问题 | 影响 | 位置 |
|---|---|---|---|
| 1 | `DEFAULT_RUNNING` 里 `"interfaces"` 键写了两次，后者覆盖前者 | 新装设备**丢掉** ethernet/wireless/bridge/wg/openvpn/tunnel/vxlan 全部默认值 | `config.py:31` |
| 2 | 19 个节点用 `Node(name="", dynamic=True)` 声明 | `neighbor`、`route-map`、`community-list`、`login user`、IPsec 全部、`vrf`、`traffic-policy shaper`、`console-server`、`policy route-redirect` **无法 set**；Tab 补全也会崩 | `tree.py:Node.add` |
| 3 | 前缀缩写只影响匹配、不影响存储路径 | `set syst host-name x` 会写出一个新的 `syst` 子树，真实配置纹丝不动 | `tree.py:walk` / `cli.py` |
| 4 | 叶子值无校验，剩余 token 被直接拼进值 | `set system ntp server 1.2.3.4` 存成 NTP 服务器 `"server 1.2.3.4"`；`subnet ... default-router ...` 被整段当成 subnet 值 | `tree.py:validate_value` |
| 5 | candidate 不落盘 | README 承诺"重启后仍保留"，实际退出即丢 | `config.py:_persist_candidate` |
| 6 | commit **先写 running.json，再下发** | 下发失败时 JSON 已宣称"已生效"；冲突检查还会先改内存再回滚 | `config.py:commit` |
| 7 | 配置、快照默认 0644 | WireGuard 私钥、IPsec PSK、用户密码全局可读 | `config.py:_dump` |
| 8 | 重启后残留 `rollback.conf` | `commit confirm` 会谎称"已确认"，实际没有任何定时器 | `config.py:pending_rollback` |
| 9 | 渲染把 `None`/空串输出成 `set x None` | `show configuration commands` 回放会把字符串 `"None"` 写进配置；含空格的值没有引号 | `config.py:render_*` |
| 10 | bridge VLAN 的 `untagged/tagged` 是标量时按字符遍历 | 真机现场：`ports='e:u*' 't:u*' 'h:u*' '1:u*'`（`eth1` 被逐字符展开） | `config.py:_as_list` |
| 11 | DHCP 树路径是 `service dhcp-server ... subnet ...`，下发读的却是 `service.dhcp.<name>` | DHCP 配置**永远不下发**（真机亦然） | `config.py:_apply_dhcp` |
| 12 | `sqm.@general[0]` / `sqm.@queue[0]`、`adguardhome.main`、`smartdns.force_aaaa` | 与真机 UCI 结构不符：sqm 是 `queue '<iface>'`，adguardhome 是 `config` 段且端口在 yaml，smartdns 无 `force_aaaa` 选项 | `config.py` |
| 13 | 用户管理调用 `chpasswd/useradd/usermod` | 真机（ImmortalWrt）**三个都不存在**，只有 `/bin/passwd` | `config.py:_apply_login` |
| 14 | KCP 调 `/etc/init.d kcp_x restart`（目录当命令） | 生成的隧道永远起不来；脚本也没 chmod +x | `config.py:_apply_kcp` |
| 15 | `tc qdisc add` 非幂等 | 第二次 commit 必失败 | `config.py:_apply_traffic_policy` |
| 16 | IPsec `modp{group*256}` → `modp3584`；remote-access 块重复；RA 的 PSK 没写进 secrets | 协商失败 / 配置自相矛盾 | `config.py:_apply_ipsec` |
| 17 | `show interface` 的 S/L 打成 `u/u`（state 打两遍）；`show version` 空硬件字段输出空行 | 输出不可读 | `op_show.py` |
| 18 | `_ensure_package` / `_ensure_ss` 死代码；`dummy`、`policy` 节点重复定义 | `policy` 重复会**覆盖**前面的 community-list（已合并）；`_ensure_ss` 会在 commit 时偷偷 opkg install | `config.py` / `commands.py` |
| 19 | 删除 cron job 后只删掉注释行，任务行残留（真机实测发现） | 被删的定时任务仍在执行；已改为整块删除，并抽出 `merge_crontab()` 做纯函数测试 | `config.py:merge_crontab` |
| 20 | 可重复叶子在旧配置上被存成标量，下发时按字符遍历（真机实测） | `set system ntp 223.5.5.5` 写进 UCI 变成 `2 2 3 . 5 . 5 . 5`；`name-server`/`push`/`network`/`port` 等同样中招 | `config.py:set_value`（按 DEFAULT 判断 list）+ `_as_list()` |
| 21 | 旧配置的 tunnel 用 `local-ip/remote-ip`，命令树只认 `source-address/remote` | `show configuration commands` 回放报 `incomplete path`，配置无法自举 | `commands.py` tunnel 模板加别名 |
| 22 | bridge 用 `type=bridge` 建在 interface 上 | netifd 自动加 `br-` 前缀：`br-vyos_br_br100` 18 字符 > IFNAMSIZ，真机日志反复报 `longer than max size 15`，bridge 永远起不来。改为 device 段 + 短设备名 | `config.py:_apply_interfaces` |
| 23 | 删除 bridge 只删 UCI 段，内核设备残留；无成员的 bridge netifd 不创建（NO_DEVICE）；dummy 需要 `kmod-dummy` | 真机验证：br9 需手工 `ip link del`；空端口 bridge 起不来；dummy 设备缺失。已加 `ip link del` 清理与"无成员"提示，dummy 依赖写入文档 | `config.py` / `DEPENDENCIES.md` |
| 24 | `_apply_nat` 直接在 `nat.destination` 下按 id 遍历，而命令树写的是 `nat.destination.rule.<id>` | section 变成 `vyos_nat_dst_rule`（id 丢失）；DNAT 又用了 `dst_dport/to_dest` 这类非 fw4 选项 → 端口转发静默失效。修复后真机生成 `dnat ip to 192.0.2.9:65001` | `config.py:_apply_nat` |
| 25 | 给已被 `lan/wan` 占用的设备再建 `vyos_<if>` | 真机 eth1（WAN）被追加了 LAN 地址 `192.168.1.1/24`。现在检测到 device 已被其它 section 占用就跳过并提示，不再制造重复接口 | `config.py:_apply_interfaces` |
| 26 | JSON 与 UCI 之间没有任何漂移可见性 | 新增 `applied.json`（记录每次 commit 写过的 section 指纹）与 `show system drift`；手工改 UCI / 恢复备份 / 升级后能看出哪些 section 被改过 | `config.py:_record_applied` / `drift` |
| 27 | 改 hostname 只写 UCI，`uci apply` 在 23.05 上不存在 | 真机验证内核主机名一直没变；改为 `uci apply`（24.10+）+ `/etc/init.d/system reload`，实测 `/proc/sys/kernel/hostname` 同步 | `config.py:_apply_hostname` |
| 28 | 漂移只能看见、不能修复 | configure 模式 `sync`：按 `applied.json` 记录的 owner **只重放漂移段落**；无漂移直接返回，旧 manifest 首次升级时退化为全量。真机验证：改 hostname 后 `Sync complete (drift sections) / hostname -> OpenWrt`，未触发 network/firewall reload；`missing` 且重放后仍未重建的 section 会从 manifest 中剪掉（例如手工删除的 wg 接口） | `config.py:sync` / `_apply_steps` |
| 29 | `interfaces ethernet <if> address` 对已有 lan/wan 设备只能"跳过" | 引入 `_network_map()`：直连设备且 proto 为 static/none 时接管现有 section；DHCP/PPPoE 与桥端口明确拒绝并提示；同时统一了 `interfaces lan device` 与 `interfaces.role` 两种写法 | `config.py:_network_map` / `_apply_interfaces` / `_apply_interface_roles` |
| 30 | WireGuard 把 `host:port` 整段写进 `endpoint_host`；删除接口不清理 UCI/内核设备 | 真机 wg 报 `Name does not resolve: [192.0.2.10:51999]:51820`，peer 建不出来；删除后 `network.wg*` 与 `wg*` 设备残留。已拆分 endpoint_host/port、按类型清 peer、`ip link del` | `config.py:_apply_wireguard` |
| 31 | BGP 通过 UCI `frr.*` 下发，但该固件的 frr 包**没有 /etc/config/frr** | 配置永不生效。改为生成 `/etc/frr/frr.conf` + 打开 `daemons` 的 zebra/bgpd，真机 `vtysh -d bgpd -c "show bgp summary"` 验证 AS65001/邻居/network；community-list 需 `expanded` 语法 | `config.py:render_frr_conf` |
| 32 | IPsec peer 存在 `vpn.ipsec.site-to-site.peer` 下却没读；`ike=`/`esp=` 写成 group 名；`config setup:` 多冒号；没有 teardown | 真机 `ipsec statusall` 看不到连接。改为按 group 展开算法串、去掉 group 伪 conn、删除时清空 secrets，验证到 `peer-203.0.113.5 ... child: 10.1.0.0/24 === 10.2.0.0/24` | `config.py:_apply_ipsec` |
| 33 | console-server / wireless 的真实链路 | conserver 真机验证：生成 `conserver.cf` 并启动；本机**无无线硬件**，`wireless` 仍未验证 | `config.py:_apply_console_server` |
| 34 | 开机时 JSON 与 UCI 没有对账入口 | `init.d` 的 `boot()` 后台执行 `vyoscli --sync`：无漂移时一行日志即结束，有漂移只重放相关 step；真机 `boot` 验证日志 `Sync: no drift`，init 已 enable（S99/K10） | `init.d/vyoscli` / `__main__.py:--sync` |
| 35 | 整段删除 `system.ntp` 后重建失败；apply 失败时 drift 记录会被误剪 | `uci set system.ntp.enabled` 在 section 不存在时报错，改为先 `uci set system.ntp=timeserver`；`sync` 在有 `failed` note 时不再剪 manifest | `config.py:_apply_system_meta` / `sync` |
| 36 | 报错提示 `try '?'`，但 CLI 从不处理 `?` | 实现 VyOS 风格内联帮助：`show ?`、`set system ?`、`?` 都按当前节点列出子命令/参数；`exit`/Tab 仍走原路径 | `cli.py:_help_text` |
| 37 | 规范化 edit 路径后 `edit system` 失效（cfg_root 下是 `set/delete/edit` 动词，不是配置树） | `edit/next` 改为以 `set` 为根解析并回写 canonical path；补了 `edit system` + `set host-name` 组合、缩写 `edit syst` 的测试 | `cli.py:_run_cfg` / `_matches_with_help` |
| 38 | console-server 的 per-device dropbear 用 `kill "$(cat ...)"` 的 shell 写法，pid 文件也没人读 | 改为读 pidfile + `os.kill`；真机验证 `ssh-port 2222` 后 dropbear 监听、删除后 pidfile 与端口都清理 | `config.py:_apply_console_server` |
| 39 | 无 `/etc/config/wireless` 时 `uci set wireless...` 直接报错 | 无射频设备改为跳过并提示（不再创建残缺配置）；本机仍无法做无线端到端验证 | `config.py:_apply_wireless` |
| 40 | `sync` 全量路径会 `podman rm -f` 重建所有容器 | 全量 sync 跳过 `containers` 并在输出中说明；定向 sync 不受影响 | `config.py:sync` / `_apply_all` |
| 41 | 接管现有静态接口是"就地改"，原 proto/地址不可恢复 | 首次接管前把 `proto/ipaddr/device/ifname` 备份到 `/etc/vyoscli/backup/network.<section>.json`（0600）；地址清空或设备从配置移除时自动还原并删除备份；自建的 `vyos_*` 接口则整段删除。真机验证：`192.0.2.1/24` 被接管为 `192.0.2.5/24`，删除后恢复原值 | `config.py:_backup_section` / `_restore_section` / `_release_iface` |
| 42 | 命令树、类型、help 在 `commands.py` 里手写三遍，与默认值/下发易漂移 | 引入 `schema.py`：`Spec(path, type, help, repeatable)` 一行定义一条路径；`system` 与 `interfaces ethernet` 两棵子树已改为 schema 生成（其余逐步迁移），新增 `tests/test_schema.py` 保证每条 spec 都能 set 且类型/默认值一致 | `schema.py` / `commands.py` |
| 43 | `service` 下的简单叶子（ssh/adguard/dnsmasq/smartdns 标量/tcp-accelerate/sqm）同样是手写三份 | 迁移到 `schema.SERVICE`（26 条），删掉对应手写块；动态子节点（smartdns server/domain-set、crontab、kcp、console-server、dhcp-server）保持手写，真机验证 `set service ?` 与动态路径仍正常 | `schema.py` / `commands.py` |
| 44 | bridge/tunnel/vxlan/loopback/dummy 的模板字段同样是手写 | 迁移到 `schema.TEMPLATES`（5 组、38 条），`schema.template()` 生成动态模板；bridge 的 vlan 子节点保持手写。真机验证 `set interfaces bridge ?` 与 tunnel 老键 `local-ip/remote-ip` 仍可用 | `schema.py` / `commands.py` |
| 45 | 动态节点（bridge/vlan/peer…）在 `?`/Tab 下没有任何提示 | 没有候选时补 `<name>` 提示，并且不再对动态节点误报 `<Enter>` | `cli.py:_matches_with_help` |
| 46 | firewall zone/forwarding/rule 与 nat source/destination rule 的模板字段同样手写 | 迁移到 `schema.TEMPLATES`（新增 5 组、15 条），`?` 真机验证 `firewall zone` / `firewall rule` / `nat destination rule` 的字段提示正常 | `schema.py` / `commands.py` |
| 47 | `commands.py` 里约 700 行手写配置树，字段/help 三份冗余 | 整棵配置树改为生成数据：`config_tree.py`（353 个节点、49 个动态模板，JSON 内嵌）+ `schema.build_tree()` 构建；`commands.py` 从 1120 行降到 329 行。先用脚本导出旧树做基线，重建后 354 条记录逐项一致；真机抽查 DHCP/route-map/ipsec/wireguard/bgp/community-list 深路径均正常。动态节点 Tab 候选改为通用 `<name>` 提示（不再列现有实例名） | `config_tree.py` / `schema.py` / `commands.py` |
| 48 | 全量生成后动态节点的 Tab 候选退化为 `<name>` | `build_tree(store=...)` 把动态节点的配置路径传入，候选改为从 `candidate` 取现有实例名（`eth0/eth1/br9/…`）；节点只在其祖先路径可解析时生效。另修合成节点与动态候选重复（walk 缓存的 `_synthetic` 节点不再出现在补全里） | `schema.py:build_tree` / `cli.py` / `tree.py` |
| 49 | 命令清单靠手写，和 353 节点配置树容易漂移 | 新增 `scripts/gen-command-reference.py`，从 `config_tree.py` 生成 `docs/COMMANDS.md`（223 条命令，每条含说明与可运行示例）；README 增加操作模式/配置模式/配置树速览与示例，并加测试校验参考文档与叶子数量一致 | `scripts/gen-command-reference.py` / `docs/COMMANDS.md` / `README.md` |
| 50 | 缺少自动化：单测/文档一致性/打包都靠手工 | 新增 `.github/workflows/ci.yml`（单测 + `check-generated.sh` 校验 `docs/COMMANDS.md` + 无 SDK 打包）与本地脚本 `scripts/check-generated.sh`；README 增加 CI 说明 | `.github/workflows/ci.yml` / `scripts/check-generated.sh` |
| 51 | 与 VyOS 1.5 的功能差距没有量化 | 新增 `docs/VYOS-GAP.md`：按 14 个顶层章节对比（接口/防火墙/NAT/策略/协议/服务/系统/VPN/HA/LB/PKI/QoS/容器/VRF），标注 ✅/🟡/❌，给出 P0–P2 路线与 OpenWrt 可行性（keepalived/haproxy/FRR/strongSwan 等包），并指出 `config_tree.py` 已成为事实源的技术债 | `docs/VYOS-GAP.md` |
| 52 | firewall 只有 zone 模型，缺少 VyOS 1.5 的方向化规则 | 新增 `firewall ipv4/ipv6 input/forward/output filter rule <n>`（action/protocol/state/inbound-interface/source/destination/port/address-group/port-group/log/disable）与 `firewall group`，渲染到独立 nft 表 `vyos_fw`（priority -10，先于 fw4，accept 继续走 fw4）；真机验证 drop 9999 规则生效、删除后表消失 | `config_tree.py` / `config.py:_apply_firewall15` |
| 53 | NAT 依赖 fw4 的 zone 名称（硬编码 lan/wan），字段也不全 | 改为 VyOS 风格 nft NAT：source/destination 规则支持地址/端口/协议匹配、`translation address/port`、静态 1:1、`hairpin`、log/disable，渲染到 `inet vyos_nat`（dstnat-10/srcnat-10，先于 fw4）；真机验证 DNAT 18080→192.0.2.1:80 生成两条（hairpin）规则、删除后表消失 | `config.py:render_nat_nft` / `_apply_nat` |
| 54 | `firewall global-options` 只是存 JSON，没有实际效果 | `all-ping`/`broadcast-ping`/`syn-cookies`/`log-martians` 映射为 `sysctl -w`；`state-policy established/invalid` 渲染为 nft 链首的 `ct state ... accept/drop`；真机验证 syncookies=1、状态规则生效 | `config.py:render_firewall_nft` / `_apply_firewall15` |
| 55 | system 只有 hostname/DNS/NTP 等，缺运维基础项 | 新增 `system syslog`（local/console/remote→logd）、`system conntrack`（table-size/timeout→nf_conntrack sysctl）、`system sysctl parameter`、`system watchdog`（module→modprobe，超时值仅存储）；真机验证 log_ip/log_port/conloglevel 与 3 条 sysctl 生效 | `config_tree.py` / `config.py:_apply_system_extra` |
| 56 | policy 只有 community-list，route-map match/set 很少 | 新增 `policy access-list/prefix-list/as-path-list`（动态列表+规则）并扩展 route-map 的 match（prefix-list/as-path/metric/tag）与 set（metric/tag/weight/next-hop/origin）；`render_frr_conf` 输出 prefix-list/as-path/access-list 与 `match ip address prefix-list`；frr 重启超时 20s→60s。单元测试覆盖渲染；**真机验证被操作策略拒绝，待补** | `config_tree.py` / `config.py:render_frr_conf` / `_apply_bgp` |
| 57 | protocols 只有 static/bgp，没有 OSPF/RIP/BFD | 新增 `protocols ospf`（router-id/log-adjacency-changes/default-information/area network/interface cost+priority+passive）、`protocols rip`、`protocols bfd`；`render_frr_conf` 输出 router ospf/rip/bfd，`_set_frr_daemons` 控制 ospfd/ripd/bfdd。frr 重启会挂起，改为 `/etc/init.d/frr start` + `vtysh -b`；真机验证 ospf/rip 配置进入 running-config、daemons 开关与删除清理 | `config_tree.py` / `config.py:render_frr_conf` / `_apply_bgp` |
| 58 | service 缺 NTP/LLDP 等基础服务 | 新增 `service ntp`（server 列表→`system.ntp.server`，重启 sysntpd）与 `service lldp`（interface 列表/description→UCI lldpd）；真机验证 ntp server 写入、lldpd 运行与描述、删除后清理，并从 JSON 全量 sync 恢复原 NTP | `config_tree.py` / `config.py:_apply_ntp` / `_apply_lldp` |
| 59 | 缺 SNMP 管理面 | 新增 `service snmp`：community→com2sec/com2sec6/group(v1/v2c/usm)/access，contact/location→system，listen-address/port→agentaddress；真机验证 snmpd 监听 1610、UCI 生成与删除清理 | `config_tree.py` / `config.py:_apply_snmp` |
| 60 | 缺 IPv6 RA 配置 | 新增 `service router-advert interface`（prefix/managed-flag/default-lifetime/no-send-advert）；映射到 UCI `dhcp.<if>` 的 ra/dhcpv6/ra_management/ra_lifetime 并重启 odhcpd；应用前备份原值、删除时还原。真机验证 lan 上 RA 生效、删除后 ra=server 恢复且 drift 清零 | `config_tree.py` / `config.py:_apply_router_advert` |
| 61 | 没有 API 管理面 | 新增 `service https`（port/listen-address/api-key）与 `vyoscli.api` 只读 HTTP API（/api/version、/api/configuration、/api/show?path=），Bearer 鉴权、进程 pidfile 管理；真机验证 200/401、/api/show 取值、删除后端口关闭。**TLS 未实现**（等 PKI）；另 `dhcp-relay` 仅有 isc 二进制且 67 端口与 dnsmasq 冲突，暂不做 | `api.py` / `config.py:_apply_https` |
| 62 | 缺 VRRP/高可用 | 新增 `high-availability vrrp`（group：interface/vrid/address/priority/preempt/hello-source/peer-address/track；sync-group；global-parameters startup-delay），生成 `/etc/config/keepalived` 的 vrrp_instance/ipaddress/peer/vrrp_sync_group；同时给命令树加 repeatable 叶子支持（address 列表）。真机验证 VIP 192.0.2.250/24 在 br-lan 上进入 MASTER、删除后 VIP 移除 | `config_tree.py` / `config.py:_apply_vrrp` / `cli.py` / `schema.py` |
| 63 | 没有证书/私钥存储，TLS/VPN 无凭据可用 | 新增 `pki`（ca/certificate/key-pair/dh），证书/私钥写入 JSON 并落盘到 `/etc/vyoscli/pki/<kind>/<name>.{crt,key,pub,pem}`，私钥 0600，删除配置时清理文件；真机验证文件生成/权限/删除。ACME 与 `generate pki` 未做，API 的 TLS 待有证书生成能力后再接 | `config_tree.py` / `config.py:_apply_pki` |
| 64 | QoS 只有自研的 traffic-policy shaper，结构不对 | 新增 VyOS 风格 `qos policy shaper/limiter/fq-codel/cake` + `qos interface ingress|egress`，渲染为 tc（htb/fq_codel/cake/ingress police）；真机验证 br-lan 上 fq_codel 生效、删除后恢复 noqueue。L2TP/SSTP/OpenConnect 服务器端缺证书生成/配套包，本轮未做 | `config_tree.py` / `config.py:render_qos_commands` / `_apply_qos` |
| 65 | 没有 IPv6 NAT | 新增 `nat66 source|destination rule`，复用 nat44 渲染器（family=ipv6，`ip6 saddr/daddr`、IPv6 目标加方括号），写入 `inet vyos_nat66`；真机验证 DNAT [2001:db8::10]:80 规则与删除清理。nat64/cgnat 需 Jool/SIIT，OpenWrt 无对应模块，记录为不可行 | `config_tree.py` / `config.py:render_nat_nft` / `_apply_nat66` |
| 66 | 没有负载均衡 | 新增 `load-balancing haproxy`（global-parameters max-connections、service frontend、backend server），生成 `/etc/haproxy.cfg` 并先 `haproxy -c` 校验，失败回滚；首次改写前备份原配置，清空后还原。真机验证监听 127.0.0.1:18080、删除后端口关闭、原 cfg md5 恢复 | `config_tree.py` / `config.py:render_haproxy_cfg` |
| 67 | 缺 VTI/Geneve 等虚拟接口 | 新增 `interfaces vti` / `interfaces geneve`，用 `ip link add ... type vti|geneve` + `ip addr replace` 下发，删除时 `ip link del`；创建失败会输出 `create failed: Unknown device type`。**测试镜像内核没有 vti/geneve 模块，无法真机跑通**；bonding/macsec/wwan 需要额外网卡/硬件，未做 | `config_tree.py` / `config.py:_apply_virtual_ifaces` |
| 68 | 缺 NetFlow 流量统计 | 新增 `system flow-accounting`（interface 列表 + netflow server），每个接口生成一个 softflowd UCI 实例（host_port/export_version/pid_file），重启 softflowd；sFlow 提示 softflowd 不支持。真机验证 vyos_fa_0 生成、进程带 `-i br-lan -n 127.0.0.1:2055` 运行、删除后进程消失 | `config_tree.py` / `config.py:_apply_flow_accounting` |
| 69 | `config_tree.py` 是"一次性生成"的数据，注释却写着勿手改，源缺失 | 把树数据移到 authored 源 `schema/config-tree.json`，新增 `scripts/build-config-tree.py`（校验重复名/类型/dyn 模板/type+children 冲突并生成 `config_tree.py`）；`check-generated.sh` 同时校验两件生成物，新增 `tests/test_tree_source.py` 校验树与源一致 | `schema/config-tree.json` / `scripts/build-config-tree.py` |
| 70 | API 只有明文 HTTP；单行 PEM 也不是合法证书格式 | `service https` 新增 `certificate <pki 名称>`，`api.py` 支持 `--cert/--tls-key` 并包 SSL socket；pki 写文件时把单行 PEM 按 64 列换行（`_format_pem`）。真机验证 HTTPS 200/鉴权、端口关闭、证书文件清理。另：bonding 内核无 `bonding.ko`，`ip link add type bond` 报 Unknown device type，记录为不可行 | `api.py` / `config.py:_apply_https` / `_format_pem` |
| 71 | 缺 OpenConnect 服务端 | 新增 `vpn openconnect`（port/network/max-clients/dpd/user），映射到 OpenWrt ocserv UCI（enable/port/auth=plain/ipaddr/netmask + ocservusers），重启/停止 ocserv；真机验证 TLSv1.3 握手、监听 18443、删除后进程与端口清理 | `schema/config-tree.json` / `config.py:_apply_openconnect` |
| 72 | 迭代收尾 | P0/P1/P2 可落地项已实现（106 个用例），剩余项均为镜像限制或操作策略阻塞：L2TP/SSTP、dhcp-relay、bonding/macsec/wwan、VTI/Geneve、MPLS/SR、nat64/cgnat、WAN 多线、policy 真机验证。详见 docs/VYOS-GAP.md 最终状态 | — |
| 73 | bonding 未实现，VTI/Geneve 因缺模块被误判不可行 | 安装 `kmod-bonding`/`kmod-geneve`/`kmod-macsec`/`kmod-ip-vti` 后：VTI/Geneve 真机验证通过（vti0/gnv0 地址链路正常）；新增 `interfaces bonding`（mode/hash-policy/member/address/mtu/disable），成员先 down 再 enslave，bond0 + dum0/dum1 真机验证 802.3ad 与地址。policy 验证仍被面板策略拒绝 | `schema/config-tree.json` / `config.py:_apply_bonding` |
| 74 | 缺 MACsec | 新增 `interfaces macsec`（source-interface/cipher/key/address/mtu/disable），`ip link add ... type macsec` + `ip macsec add tx sa`；真机验证 macsec0@dum0、GCM-AES-128、地址 10.96.0.1/24，删除后链路消失（内核把 key 显示为掩码） | `schema/config-tree.json` / `config.py:_apply_macsec` |
| 75 | 缺 L2TP 服务端 | 新增 `vpn l2tp`（port/local-ip/pool-start/end/name-server/user），生成 xl2tpd.conf、options.xl2tpd、chap-secrets（0600），首次改写前备份原文件，禁用时还原并停止 xl2tpd；真机验证 UDP 1701 监听、删除后端口关闭且原配置恢复 | `schema/config-tree.json` / `config.py:_apply_l2tp` |
| 76 | 缺 DHCP relay | 新增 `service dhcp-relay`（server/interface/upstream-interface），生成 `/etc/dhcp-fwd.conf` 并启动 dhcp-fwd；真机验证 0.0.0.0:67 监听、删除后进程退出；测试时临时 `dhcp.lan.ignore=1` 让出 67，随后恢复 dnsmasq 并确认 dhcp-range 重新生成、No drift | `schema/config-tree.json` / `config.py:_apply_dhcp_relay` |
| 77 | WAN 多线负载未做 | 新增 `load-balancing wan`（interface weight/track-ip、rule），映射到 mwan3 的 interface/member/policy/rule；未安装 mwan3 时安全拒绝、不改任何状态（真机验证提示 + 无 mwan3 改动）。真正启用需安装 mwan3 并接受其接管路由/防火墙的风险 | `schema/config-tree.json` / `config.py:_apply_wan_lb` |
| 79 | show interface 输出含内核伪接口、详情重复；无 Tab 候选；help 提示是 name/value；SSH 无源 ACL | `show interfaces` 改为 VyOS 表格（Interface/IP Address/S/L/Description），只列配置接口+物理口并过滤 gre0/dummy0/tunl0 与 @NONE；详情只追加 RX/TX 统计；新增 `_completion` 支持，`show interfaces ethernet <TAB>` 列出网卡；值提示改为 `<x.x.x.x/xx>` 等 VyOS 占位符，动态节点按上下文显示 `<ifname>/<br-name>`；`service ssh access-control allow|deny address` 渲染 nft `inet vyos_ssh`（allow 在 deny 前）。真机验证 ACL 规则与删除清理 | `cli.py` / `op_show.py` / `commands.py` / `config.py:_apply_ssh_acl` |
| 80 | BGP 邻居建立后前缀被丢弃 | FRR 10 默认 `ebgp-requires-policy`，且邻居未在 IPv4 AF 中 activate，`show bgp summary` 显示 `(Policy)`。render_frr_conf 现在总是输出 `address-family ipv4 unicast` + `neighbor <ip> activate`，并加 `no bgp ebgp-requires-policy`。真机与 ExaBGP（192.168.75.244，AS65000）邻居 Established，PfxRcd 从 `(Policy)` 变为 0 | `config.py:render_frr_conf` / `tests/test_apply.py` |
| 81 | 缺 soft-reconfiguration / show ip bgp | 新增 `protocols bgp neighbor <peer> soft-reconfiguration inbound`（渲染到 IPv4 AF，真机显示 Inbound soft reconfiguration allowed）；新增 op 命令 `show ip bgp summary` / `show ip bgp table`，直接调用 vtysh 输出。真机 OpenWrt 已收到 ExaBGP 6204 条前缀并装表 | `schema/config-tree.json` / `config.py:render_frr_conf` / `op_show.py` / `commands.py` |
| 82 | show 输出一次性刷屏 | 所有命令输出统一走 VyOS 风格分页器：TTY 下按终端高度分页，空格/回车下一页、b 上一页、q 退出；非 TTY（管道/脚本）不分页。真机 pty 验证 --More-- 与 q 退出，6204 条路由只输出一页 | cli.py:_print_output |
| 83 | 缺 show arp | 新增 show arp，解析 ip neigh 输出为 VyOS 表格（Address / HWtype / HWaddress / Flags Mask / Iface），仅 IPv4；真机输出与 VyOS 对齐 | op_show.py:_op_show_arp / commands.py |
| 84 | show ip route 输出是 Linux 格式 | show ip route / static / connected / summary 优先调用 
| 85 | 缺 show ip route bgp | 新增 show ip route bgp，优先 
| 86 | 缺 show ip bgp neighbors | 新增 show ip bgp neighbors（动态补全邻居 IP、详情走 show bgp neighbor <ip>）和 ... <ip> received-routes（show bgp ipv4 unicast neighbors <ip> received-routes）；真机补全列出 192.168.75.244，详情与接收路由表正常 | op_show.py / commands.py / cli.py |
| 87 | 缺 policy local-route / 静态路由表 | 新增 policy local-route rule <n> source <ip> set table <id> 和 protocols static table <id> route <prefix> next-hop <ip>：下发 ip rule add from <src> lookup <table> priority <n> 与 ip route replace table <id> ...，变更时清理旧规则；新增 show policy local-route。真机验证 rule 6600/table 110 出现并在删除后清理 | config.py:_apply_local_route / _apply_static_tables / op_show.py |
| 88 | 缺 show dhcp server | 新增 show dhcp server（服务状态/网络数/池/租约/静态数）、... pools（范围与 Used/Total）、... leases（解析 /tmp/dhcp.leases）、... static（静态绑定）。配置优先读 vyoscli running config，未配置时回退解析 UCI dhcp；真机输出 dnsmasq 运行、lan 池 192.168.1.100-249（0/150） | op_show.py / commands.py |
| 89 | show container image 只认 podman | 改为自动探测 podman/docker/nerdctl，并用 --format table 输出 REPOSITORY/TAG/IMAGE ID/CREATED/SIZE；无运行时时明确提示。真机（无容器运行时）输出提示 | commands.py:_op_show_container_image |
| 90 | podman --format 表头异常 | show container image 改用运行时原生 images 输出（REPOSITORY/TAG/IMAGE ID/CREATED/SIZE）。真机安装 podman 4.9.3，因 registry-1.docker.io 被劫持改用 docker.m.daocloud.io 镜像，成功列出 busybox | commands.py:_op_show_container_image |
| 91 | 缺 show login user | 新增 `show login user`：解析 `ss -tnp`（无 ss 时回退 `netstat -tnp`）的 22 端口已建立连接，列出 Username/IP Address/TTY/Login Time；登录时间优先 ps，回退 /proc。真机列出两个 root SSH 会话及时间 | `op_show.py:_op_show_login_user` |
| 92 | show login user 看不到 console/vty | 改为枚举 /proc 中带 TTY 的登录 shell（console/ttyS0/tty1/pts），TTY 名取自 fd/0 链接，用户取自进程；pts 会话通过父进程链关联 SSH 对端 IP，无 TTY 的 SSH 连接再按 netstat 兜底。真机列出 `pts/0`（192.168.75.78）和 `tty1`（本地控制台） | `op_show.py:_op_show_login_user` |
| 93 | 缺 show login（当前会话） | 新增 `show login`：输出 login/user/level/groups，TTY 取 `os.ttyname(0)`（非 TTY 为 `-`），IP 沿父进程链匹配 SSH 连接，登录时间取会话进程；组从 /etc/passwd + /etc/group 解析。真机输出 root / admin / root / 192.168.75.78 | `op_show.py:_op_show_login` |
| 94 | 无法踢掉在线 SSH 用户 | 新增 op 命令 `disconnect user <name>` 和 `disconnect ssh <ip>`：枚举 SSH 会话（pts 登录 shell + dropbear 父进程 / 非 TTY 连接），匹配后向 dropbear 与 shell 发 SIGTERM；默认跳过当前会话。真机验证命令与补全，无匹配时提示 no matching SSH sessions | `op_show.py:_disconnect_sessions` / `commands.py` |
| 95 | disconnect ssh 参数形式 | `disconnect ssh` 下增加 `user <name>` 与 `ip <addr>` 子命令，同时保留 `disconnect ssh <ip>` 直接写法；真机验证三种形式补全与提示 | `commands.py` |
| 96 | 无法按 TTY 踢人 | `disconnect ssh <pts/N|ttyN>` 直接按 TTY 匹配，另加 `disconnect ssh tty <tty>` 子命令；真机验证补全与 no matching 提示 | `op_show.py:_op_disconnect_ssh` / `commands.py` |
| 97 | 缺 service ssh acl permit / disable-host-validation | 新增 `service ssh acl permit <prefix>`（可重复）与 `service ssh disable-host-validation`。acl permit 渲染为 nft `inet vyos_ssh` 的 allow-list：`set permit` + `ip saddr @permit accept` + 默认 drop；真机配置 192.168.75.0/24 后 SSH 保持在线，删除后表清理。disable-host-validation 仅保存（dropbear 无对应项） | `schema/config-tree.json` / `config.py:_apply_ssh_acl` |
| 98 | ethernet mtu 未下发、缺 tcp-mss | `interfaces ethernet` 增加 `tcp-mss`，并让 `mtu` 真正执行 `ip link set <if> mtu`（删除时回 1500）；`tcp-mss` 渲染 nft `inet vyos_mss` 的 forward/output MSS clamp。真机 eth1 mtu 1400->1500、tcp-mss 1300 规则出现并在删除后清理 | `config.py:_apply_interfaces` / `_apply_tcp_mss` |
| 99 | tcp-mss/mtu 改为 OpenWrt 原生 | `tcp-mss` 不再建独立表，改为生成 `/etc/nftables.d/20-vyos-mss.nft`（forward/output，priority mangle），`fw4 reload` 生效、删除时 `fw4 restart`；`mtu` 同时写 `network.<section>.mtu`（优先 IPv4 section，避免落到 wan6）再 `ip link set`。真机验证 wan.mtu=1400、fw4 链、mtu 1400/1500 与删除清理；commit network 会造成 WAN 短暂 down/up | `config.py:_apply_tcp_mss` / `_apply_interfaces` |
| 100 | 缺 show system cpu/image/login users/connections | 新增 `show system cpu`（/proc/cpuinfo 拓扑）、`show system image`（+ storage/version）、`show system login users`（passwd/shadow + 当前会话）、`show system connections`（+ tcp/udp，netstat -a）。真机验证 CPU/镜像/账户/TCP/UDP 输出 | `op_show.py` / `commands.py` |
| 101 | op 缺 TCP/UDP 端口探测 | 新增 `ping tcp <ip> <port>` 与 `ping udp <ip> <port>`：TCP 用 connect 测连通/拒绝/超时；UDP 发送1 字节并区分 reply、ICMP unreachable、no response。真机验证 22 连通、2707 refused、UDP 53 no response、UDP 9 closed | `op_show.py:_op_ping_tcp` / `_op_ping_udp` |
| 102 | UDP 探测只发 1 字节不可靠 | `ping udp` 改为按端口构造可触发回包的报文：53 DNS（version.bind）、123 NTP、3478 STUN、7 echo，其余发 1 字节；支持自定义 payload 与 `hex:`。真机 UDP/53 得到 dns reply，UDP/9、UDP/9999 得到 ICMP closed | `op_show.py:_udp_payload` / `_op_ping_udp` |
| 103 | UDP 探测仍引用 ICMP unreachable | `ping udp` 不再从 ICMP 错误推导端口状态：只有收到协议回包才判 open，超时/拒绝统一报 `no reply (open|filtered)`，输出中不出现 ICMP 字样。真机 UDP/53 得到 dns reply，UDP/9 得到 no reply | `op_show.py:_op_ping_udp` |
| 104 | 多出口无法记录断在哪一跳 | 新增 `monitor path <target>`（支持 interface/source/count/interval/max-hops）：按出口跑 traceroute 逐跳记录 RTT，写 `/etc/vyoscli/monitor/path.jsonl`；再用 ICMP ping 校验目标可达，区分“真断”与“探测被过滤”，`show monitor path` 汇总各线路最近状态与断点。真机 eth1 -> 1.1.1.1 记录 7 跳并判定 reached yes | `op_show.py:_op_monitor_path` / `_op_show_monitor_path` |
| 105 | 缺少后台多任务路径监控 | 新增 `service path-monitor task <name>`（target/interface/interval/max-hops/disable）：每个任务以独立 shell 循环后台运行 `monitor path`，日志写到 `/etc/vyoscli/monitor/<task>.log`，逐跳记录写 `/etc/vyoscli/monitor/path.jsonl`；`show service path-monitor [task]` 显示运行状态、最近一跳与断点；disable/delete 会停止进程。真机验证任务启动、日志、断点、disable、delete | `config.py:_apply_path_monitor` / `op_show.py` |
| 106 | 缺 MTR 后台任务 | 新增 `service mtr <name>`（target/interface/count/interval/max-hops/disable）：后台循环 `mtr -r -n -c ... -i 1`，报告写 `/etc/vyoscli/mtr/<name>.log`；`show service mtr [name]` 解析最近完整报告，显示每跳 Loss%/Avg 与断点；disable/delete 停止进程。真机验证 wan1 运行、逐跳（含 ??? 跳）、disable/delete | `config.py:_apply_mtr` / `op_show.py` |
| 107 | `set ... disable` 必须带 true | bool 叶子支持只写关键字：`set service mtr wan1 disable` 等价于 true；`delete service mtr wan1 disable; commit` 会重新启动后台任务。真机验证 disable -> disabled、delete disable -> running | `cli.py:_apply_set_delete` / `config.py:_apply_mtr` |
tysh -c "show ip route bgp"，回退 ip route show proto bgp；真机输出 Codes 头 + B>* 条目（6204 条） | op_show.py:_op_show_ip_route_bgp |
tysh，输出 VyOS/FRR 风格（Codes 头 + S>* 等）；FRR 未运行或表为空时回退到 ip route，静态表为空时保留 Codes 头。真机 static 显示 Codes 头，full 表为 FRR 格式 | op_show.py:_vtysh_route |
| 78 | WAN 多线映射错误且 mwan3 不可用 | 安装 mwan3 后修正映射：设备名（eth1）先解析为 OpenWrt 网络接口名（wan），再写 mwan3.interface/member/policy/rule；真机验证 WAN/SSH 未中断，但 `mwan3 status` 中 wan 虽 online，所有 policy（含默认 balanced）均为 `unreachable`，WAN LB 不可用。已删除配置、停止 mwan3、清理 mwan3.* 漂移项；mwan3 包保留但未启用 | `config.py:_apply_wan_lb` |

另外：`op/delete` 的 bridge 实现有两套（`_apply_interfaces` 与 `_apply_interface_roles`），
后者把 dict 当列表遍历，已删除重复实现；`__main__` 的 rollback 子进程、`save()` 提示
写死 `/etc/vyoscli` 等小问题也一并修了。

### 2.3 新增测试

```
py -3.10 -m unittest discover -s tests -v
```

| 文件 | 覆盖 |
|---|---|
| `tests/test_cli.py` | 默认值、set/delete、校验、候选持久化、渲染回放、commit/discard/rollback、补全 |
| `tests/test_paths.py` | 50+ 条路径的"可达矩阵"；`DOC_DRIFT` 列表锁定"文档写了但树里没有"的命令 |
| `tests/test_apply.py` | 用 mock 替换 `uci`/`init.d`，断言 commit 生成的**确切 argv**（hostname、接口、静态路由、ssh、firewall、DHCP、回滚顺序） |
| `tests/harness.py` | 进程内驱动 CLI，跨平台、无第三方依赖 |

`test_paths.py` 的思路值得保留：**每条文档里的命令，要么在 REACHABLE 里，要么在
DOC_DRIFT 里显式承认不支持**，不允许悄悄失效。

---

## 3. 真机验证（ImmortalWrt 23.05.2 / Python 3.11.7）

第一阶段只做"读 + 解析 + 渲染"；随后用当前源码打出 ipk 安装到设备，做了**真实 commit**：

- `show version` / `show interface` / `set` / `compare` / `show configuration` 正常；
- 带子命令的树（DHCP shared-network → subnet → range、BGP neighbor、IPsec proposal）
  解析与渲染正确；
- Tab 补全在真机 readline 下正常，含值提示（`a.b.c.d/prefix`）；
- 13 MB RSS、0.07 s import，可接受；
- **commit 实测**：`set system host-name` → `commit` 返回
  `hostname -> vyostest`，`uci get system.@system[0].hostname` 同步变化；
  `running.json` / `candidate.json` 为 `0600`，history 快照 +1；
- **commit confirmed 实测**：`commit confirmed 5` 写入 `rollback.conf`（pid + deadline），
  `commit confirm` 取消定时器、进程退出、文件删除；
- **crontab 实测**：新增 job 写入标记块并由 cron 加载；删除 job 时发现"任务行残留"的
  真机 bug（问题 #19），修复后重新验证，删除后文件为空；
- **NTP 实测**：`set system ntp 223.5.5.5` 暴露出"可重复叶子被当字符串逐字符下发"
  （问题 #20），UCI 里变成 `server '2' '2' '3' '.' ...`；修复后删除/重设两步 commit
  验证为单条 `server 'ntp.aliyun.com'`；
- **配置回放**：`show configuration commands` 导出 10 条命令，回放到临时配置目录时
  发现旧 tunnel 键名不兼容（问题 #21），加别名后回放无报错；
- **bridge 实测**：`set interfaces bridge br9 address ...` 生成 `network.br9_dev=device` + `network.vyos_br_br9.device=br9`，`ip link show br9` 存在（补一个 member 后 netifd 才创建）；删除 bridge 后 UCI 段与内核设备都被清理；现场遗留的 `vyos_br_br100` 段导致 netifd 每次 reload 报 `longer than max size 15`，已清理；
- **firewall / NAT 实测**：`firewall rule 900 dest-port 65000 DROP` 生成 nft 规则且 SSH 不受影响，删除后规则清空；DNAT 修正 schema 后生成 `dnat ip to 192.0.2.9:65001`，SNAT 生成 `masquerade comment "!fw4: vyos_src_100"`，删除后 UCI 与 nft 均清理；
- **漂移检测实测**：commit 后 `show system drift` 无输出；手工 `uci set system.@system[0].hostname` 后报告 `changed system.@system[0]`，恢复后回到无漂移；`applied.json` 为 0600；
- **sync 实测**：手工改 UCI 的 hostname 后 `show system drift` 报 `changed`，`sync` 输出 `hostname -> OpenWrt` 并把内核/UCI 主机名都拉回，随后 drift 为空；
- **WireGuard / BGP / IPsec / conserver 实测**：wg 接口+peer（endpoint 拆分）生效；frr 用 frr.conf + daemons 启动，`vtysh` 显示 AS/邻居/network/community-list；strongSwan 生成 peer conn（PSK、隧道子网）并出现在 `ipsec statusall`；conserver 生成配置并启动；设备无无线硬件，wireless 未验证；
- **开机对账实测**：`/etc/init.d/vyoscli boot` 后台执行 `vyoscli --sync`，无漂移时日志仅一行 `Sync: no drift, nothing to do.`；整段删除 `system.ntp` 后 `show system drift` 报 missing，`sync` 重建 section 并恢复服务器，drift 归零；
- **conserver per-device ssh 实测**：`ssh-port 2222` 后 dropbear 监听、pidfile 生成；删除配置后进程/端口/文件均清理；**wireless** 因无 `/etc/config/wireless`（无射频）按设计跳过；
- **接口接管备份/还原实测**：`erspan0` 上的静态接口被接管后写入 `192.0.2.5/24`，备份文件保存原 `192.0.2.1/24`；删除该地址后自动还原并删除备份；自建 `vyos_*` 接口在地址清空时整段删除；
- 包格式：OpenWrt 的 `.ipk` 是 **gzip(tar)**（`./debian-binary` + `control.tar.gz` +
  `data.tar.gz`），不是 Debian ar；`scripts/make-ipk.py` 按此格式生成，`opkg install` 通过。

同时确认了这些**真机事实**（已反映到代码修复里）：

| 事实 | 结论 |
|---|---|
| `/etc/config/sqm` 用 `config queue 'eth1'` | 原来的 `@queue[0]` 写法是错的 |
| `/etc/config/adguardhome` 只有 `enabled`、`workdir` | DNS/Web 端口在 `/etc/adguardhome.yaml`，UCI 管不到 |
| smartdns 段类型只有 `smartdns/server/client-rule/domain-rule/ip-rule` | 原代码的 `domain-set`、`address` 段类型不存在 |
| 无 `chpasswd/useradd/usermod`，只有 `passwd` | 用户管理改为自适应（adduser → useradd → passwd） |
| 现场 `network.vyos_br_br100_vlan100.ports` 是字符碎片 | 证实问题 #10 |
| `/usr/lib/vyoscli` 只剩 `__pycache__` | 设备上的包文件不完整，需要重装（见 §7） |

---

## 4. 仍然存在的问题

### P0 — 架构/语义级（建议优先处理）

1. **双事实源**：JSON 是"期望状态"，UCI 是"实际状态"，但两者没有对账机制。
   手工改 UCI、恢复备份、包升级后，`running.json` 会与设备真实配置漂移，
   而 `show configuration` 只读 JSON。建议加 `vyoscli-sync` 开机服务（幂等 apply）
   和 `show system drift`。
2. **接口模型**（已部分解决，见 #25/#29）：`_network_map()` 解析 UCI 归属后，
   直连设备且 proto 为 `static/none` 时接管现有 section；DHCP/PPPoE 与桥端口明确拒绝并提示；
   `interfaces lan device` 与 `interfaces.role` 两种写法已统一。仍未做的是"被接管 section
   的原配置备份/还原"，以及删除地址时如何安全回收 section。
3. **声明的叶子大量未下发**（见 §5 对照表）：`description/mtu/mac/speed/duplex/vrf/disable/vif`
   都只是存进 JSON。用户会以为配好了。
4. **未在设备验证的下发**：BGP（frr UCI/`frr.conf` 标记块）、IPsec（strongswan 配置格式）、
   wireless（`wlanN→radioN` 的映射假设）、conserver。这些代码在真机上大概率还有 schema 偏差。
5. **事务性**：`_apply_all` 逐段 try/except，任何一段失败都只追加一行 note，其余照常，
   commit 仍返回 "Commit complete"。建议"先 compute → 再 apply → 失败自动 rollback 到快照"，
   至少提供 `commit dry-run` 显示将要执行的命令。

### P1 — 健壮性/体验

6. 无配置锁：两个会话同时 `set` 会互相覆盖 `candidate.json`。
7. 密钥明文存 JSON（已改 0600），但 `/etc/ipsec.secrets`、`/etc/openvpn/*.conf` 仍是 0644。
8. `show configuration` 把默认值也画出来（`adguard enabled False`、`smartdns port 5333`），
   与 VyOS"只显示显式配置"的体验不同。
9. 一次 commit 里 `_apply_interfaces`、`_apply_interface_roles`、`_apply_static_routes`
   各 reload 一次 netifd，最多 3 次；建议合并为一次 commit + 一次 reload。
10. `traffic-policy` 只做总带宽，`per-ip` 未实现；`tc` 也没有 ingress/ifb 方向。
11. 动态节点的补全候选是空列表（例如 `set protocols bgp neighbor <Tab>` 无建议），
    可以枚举现有配置里的 key。
12. 无 `?` 帮助（报错却提示 `try '?'`）；错误信息中英混排、风格不统一。
13. `show dependencies` 的包清单与 Makefile 已不一致（`strongswan-minimal` vs `strongswan`、
    `sqm-scripts`、`conserver` 等），建议从一份清单生成。

### P2 — 打包/文档/工程化

14. `DEPENDS` 17 个包约 52 MB：16/32 MB flash 的设备根本装不下，且多数功能用不到。
    建议拆成 `vyoscli`（python3 + ip-full）与 `vyoscli-full`（meta，推荐 128 MB+），
    其余按需 `opkg install`（代码对缺包已经容错）。
15. `Makefile` 的 `PKG_MAINTAINER`/`URL` 还是占位符；仓库没有 `LICENSE` 文件；
    `/etc/vyoscli` 未声明 `conffiles`，升级时配置文件可能被覆盖。
16. 文档与实现漂移：本次修了 6 处命令名（`role`、`key`、`tunnel mode`、`config-file`、
    `domain-rules-file`、`crontab command`）和"按需安装"整节，但 GUIDE 仍有 1000+ 行，
    建议**由命令树生成命令参考**，文档只保留场景示例。
17. 没有 CI；`tests/` 目前只跑逻辑层，apply 层是 mock。建议加一个 `uci` 桩 +
   真机（或 QEMU）冒烟任务。

---

## 5. 声明 vs 下发对照表

图例：✅ 已下发并验证 / ⚠️ 只存 JSON 或部分下发 / ❓ 代码有但没在设备验证 / ❌ 不可达

| 配置子树 | 状态 | 说明 |
|---|---|---|
| `system host-name / name-server / dns / timezone / ntp` | ✅ | UCI system/dhcp + resolv.head |
| `system language / hardware` | ⚠️ | 仅存储/展示 |
| `system login user` | ⚠️ | 已适配 OpenWrt 工具，但路径从 `password` 改为 `authentication.plaintext-password`，需实测 |
| `interfaces ethernet <if> address` | ✅ | 复用 `ifname` 段，否则新建 `vyos_*`；设备已属 lan/wan 时拒绝重复建（真机验证） |
| `... description/mtu/mac/speed/duplex/vrf/disable/vif` | ⚠️ | 仅存储 |
| `interfaces lan/wan device` | ⚠️ | 存 `interfaces.<role>.device`，下发读 `interfaces.role`（不一致） |
| `interfaces bridge member/address/vlan` | ✅/⚠️ | 端口/VLAN 已修，`stp/priority/aging...` 仍未下发 |
| `interfaces dummy / loopback` | ⚠️ | dummy 下发 address；loopback 未下发 |
| `interfaces wireless` | ❓ | 本机无无线硬件，仍未验证 |
| `interfaces wireguard` | ❓ | UCI wireguard（`wireguard_<if>` peer 段）未在真机验证 |
| `interfaces openvpn` | ❓ | 写 `/etc/openvpn/*.conf` + UCI openvpn |
| `interfaces tunnel / vxlan` | ❓ | gre/ipip 走 UCI proto，sit/ip6ip6 未实现 |
| `protocols static route` | ✅ | `network.vyos_route_*` |
| `protocols bgp` / `route-map` | ✅/⚠️ | 真机验证（frr.conf + daemons）；route-map/community-list 已生成，复杂策略未逐一验证 |
| `policy community-list / route-redirect` | ⚠️/✅ | community-list 仅存储；route-redirect 走 nft |
| `vrf name` | ❓ | `ip link add ... type vrf`，未验证 |
| `vpn ipsec *` | ✅/⚠️ | 真机验证 site-to-site（PSK + 隧道）；remote-access 与证书模式未验证 |
| `service smartdns` | ⚠️ | main/server/domain-rule 已按真机 UCI 重写；`address`、file 型 domain-set、`forbid-aaaa` 未映射（会输出提示） |
| `service adguard` | ⚠️ | 只切 UCI `enabled`；端口在 yaml |
| `service dnsmasq / ssh / crontab / kcp / tcp-accelerate` | ✅ | kcp 修了 init.d 调用 |
| `service dhcp-server` | ✅ | 按 subnet 自动匹配接口，offset/limit 正确计算 |
| `service sqm` | ✅ | 改为 `sqm.<iface>=queue` |
| `service console-server` | ✅/⚠️ | 配置文件与服务启动已验证；per-device dropbear 与 kill 逻辑未验证 |
| `firewall zone/forwarding/rule` | ✅ | fw4 UCI |
| `nat source/destination` | ✅/⚠️ | 真机验证 DNAT/SNAT 生效；源/目的 zone 仍固定 `lan`/`wan`，未跟随 `firewall zone` |
| `container` | ⚠️ | podman rm/run，未验证 podman 在 OpenWrt 上的行为 |
| `traffic-policy shaper` | ⚠️ | 只有总带宽，per-ip 未实现 |

---

## 6. 建议的演进方案

### 6.1 用一份 schema 驱动命令树 + 校验 + 下发

现在"命令树（commands.py 1100 行）"、"默认值（DEFAULT_RUNNING）"、"下发代码（40 个
`_apply_*`）"是三份互相不知道对方存在的定义，schema 不一致正是本次一半 bug 的来源。

建议引入 `schema.py`，一条路径只写一次：

```python
Node(
    path="interfaces ethernet * address",
    type="ipv4net", repeatable=True,
    default={"lo": ["127.0.0.1/8"]},
    help="IPv4 address/prefix",
    apply=uci.iface_address,      # 或 driver 名 + 方法
    owner="network",              # commit/reload 归属
)
```

收益：命令树、补全、校验、`show configuration commands`、文档全部自动生成；
`set` 与 `apply` 不可能再对不上；测试只需遍历 schema。

### 6.2 下发层拆成 driver + 事务

```
vyoscli/
├── schema.py          # 唯一的路径/类型/默认值/归属定义
├── store.py           # candidate/running/快照/锁（flock）
├── session.py         # 交互、补全
├── drivers/
│   ├── uci.py         # 通用 uci set/commit/apply 封装
│   ├── network.py     # netifd、bridge、vlan
│   ├── frr.py  ipsec.py  wireless.py  dns.py  container.py ...
└── apply.py           # 依赖排序 + 一次 reload + 失败回滚
```

`apply.py` 的要点：
- 先算 diff，再按 owner 分组，每组只 `uci commit` + reload 一次；
- 任一组失败 → 自动 `rollback_to(snapshot)` 并以非零退出码/错误返回；
- `commit dry-run` 打印将要执行的 argv（也是最好的测试钩子）。

### 6.3 开机对账与漂移检测

- `init.d/vyoscli` 的 `boot()` 调用 `vyoscli-sync`：以 running.json 为准做一次幂等 apply
  （`old = {}`，只写自己的 section），解决"UCI 被手工改/恢复出厂"后的漂移；
- `show system drift` 对比 JSON 与 UCI，列出差异；
- 每次 commit 把 `compare` 的 diff 一并存进 `history/<ts>.diff`，便于审计。

### 6.4 交互与安全

- `configure exclusive` / flock 防并发；
- `?` 帮助、`show configuration diff`、`commit confirmed` 的 deadline 写进 prompt；
- 密码字段不落盘（存 hash，或引用 `/etc/shadow`）；外部配置文件统一 0600；
- `show configuration` 只显示显式配置（defaults 单独放 `show configuration defaults`）。

### 6.5 打包

```makefile
Package/vyoscli        # python3 + python3-readline + ip-full，约 6 MB
Package/vyoscli-full   # DEPENDS:=vyoscli + 全部可选包（meta，无文件）
```

并在 README 中给出"按功能 opkg install"的清单。本次已把"commit 时自动 opkg install"
彻底删掉（那会在管理面上做网络 IO，容易把自己卡死）。

---

## 7. 立即可做的下一步（按收益排序）

1. **修接口语义**（P0-2）：决定复用 `lan`/`wan` 还是独占 `vyos_*`，统一 `role` 的
   schema，并让 `description/mtu` 真正下发（UCI `network.<sec>.mtu`、`device` 段）。
2. **boot reconcile + drift**（P0-1）：半天工作量，能消掉"配置看起来生效、其实没有"的最大一类问题。
3. **事务性 commit + dry-run**（P0-5）：把 `_apply_all` 改成"先 diff 后 apply"。
4. **在设备上验证 BGP/IPsec/WireGuard/wireless/conserver**，修正 UCI schema；
   每验证一项，就把 `tests/test_paths.py` 的 `DOC_DRIFT` 项挪进 `REACHABLE`。
5. **拆分依赖包**（P2-14），并补 `LICENSE`、`conffiles`、CI。
6. 长期：按 §6.1 收敛到 schema 驱动，代码量会显著下降（`commands.py` 里 1000 行
   三份重复的树可以只剩一份）。

---

## 8. 迁移注意事项（老设备）

1. 这台设备此前 `/usr/lib/vyoscli` 只剩 `__pycache__`（包文件丢失），本次已用当前源码
   重新打包安装；其它机器若遇到同样现象，按 §2 的打包流程重装即可。
2. 旧 `running.json` 的结构已变：
   - `service.dhcp` → `service.dhcp-server.shared-network-name.<name>.subnet.<cidr>`
   - `service.tcp-accelerate.fq_codel` → `fq-codel`
   - 新增 `interfaces.loopback`、`interfaces.role` 未变（但下发代码仍读 `role`）
   旧数据不会被自动迁移，建议在设备上 `show configuration commands` 导出后人工对齐。
3. 现场 `network.vyos_br_br100_vlan100.ports` 的字符碎片是旧 bug 留下的，重配该 bridge
   即可被新的"先删后建"逻辑覆盖；若不再使用该 VLAN，可手工 `uci delete` 对应 section。
