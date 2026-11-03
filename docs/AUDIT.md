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
| 新增 `tests/`（4 个文件、62 个用例） | 替代根目录 15 个 `smoke_test*.py`（已删除） |
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
