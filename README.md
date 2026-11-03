# vyoscli — 类 VyOS 的 OpenWrt CLI

用 Python 实现的 VyOS 风格命令行，以 opkg 包形式安装到 OpenWrt。
保留 VyOS 的核心交互模型：**操作模式 / 配置模式**分离、
**candidate → commit → running** 事务、Tab 补全、`?` 内联帮助、`commit confirmed` 自动回滚。

纯 Python 包，不依赖 UCI 之外的框架；没有 UCI 对应项时才退化为 `ip`/`nft`/`tc` 等原生命令。

## 目录结构

```
package/vyoscli/
├── Makefile                      # OpenWrt 包定义（opkg）
├── files/
│   ├── usr/bin/vyoscli           # shell 启动器
│   ├── usr/lib/vyoscli/          # Python 包
│   │   ├── cli.py                # REPL、双模式、补全、? 帮助、命令分发
│   │   ├── tree.py               # 命令树节点、动态节点、路径解析、值校验
│   │   ├── commands.py           # op 命令 + 组装配置树
│   │   ├── schema.py             # 声明式 Spec + 树构建
│   │   ├── config_tree.py        # 生成的完整配置树数据（353 节点）
│   │   ├── config.py             # 配置库、事务、UCI/原生下发
│   │   ├── op_show.py            # show * 实现
│   │   └── __main__.py           # 入口 + 回滚定时器 / boot sync
│   └── etc/init.d/vyoscli        # 开机对账（vyoscli --sync）
schema/
└── config-tree.json              # authored 命令树（唯一手改源）
scripts/
├── build-ipk.sh                  # SDK 内一键编译
├── make-ipk.py                   # 无 SDK 快速打包（设备测试）
├── build-config-tree.py          # schema/config-tree.json -> config_tree.py
├── gen-command-reference.py      # config_tree.py -> docs/COMMANDS.md
└── check-generated.sh            # 校验生成文档是否最新（CI 用）
tests/                            # unittest（CLI / apply / schema，无第三方依赖）
docs/
├── COMMANDS.md                   # 完整命令参考（自动生成，223 条）
├── GUIDE.md                      # 场景化配置指南
├── VYOS-GAP.md                   # 与 VyOS 1.5 官方文档的功能差距与优先级
├── DEPENDENCIES.md               # 依赖清单与体积
└── AUDIT.md                      # 代码审查、已知问题、重构路线
```

## 编译与安装

```bash
# 1. 准备 SDK（版本尽量与目标固件一致；纯 Python 包对架构不敏感）
wget https://downloads.openwrt.org/releases/24.10.0/targets/x86/64/openwrt-sdk-24.10.0-x86-64_gcc-13.3.0_musl.Linux-x86_64.tar.zst
tar -I zstd -xvf openwrt-sdk-24.10.0-*.tar.zst

# 2. 一键编译（无需 sudo / menuconfig）
SDK=~/openwrt-sdk-24.10.0-x86-64_gcc-13.3.0_musl.Linux-x86_64 ./scripts/build-ipk.sh

# 3. 安装到路由器
scp bin/packages/*/base/vyoscli_*.ipk root@router:/tmp/
ssh root@router 'opkg install /tmp/vyoscli_*.ipk'
```

手工编译等价步骤：

```bash
cd openwrt-sdk-*/
mkdir -p package/utils && cp -r /path/to/repo/package/vyoscli package/utils/
make defconfig
sed -i 's/^# CONFIG_PACKAGE_vyoscli is not set/CONFIG_PACKAGE_vyoscli=y/' .config
make defconfig && make package/utils/vyoscli/compile V=s
find bin/packages -name 'vyoscli*.ipk'
```

### 无 SDK 快速打包（仅用于设备测试）

```bash
python3 scripts/make-ipk.py --minimal-deps    # -> dist/vyoscli_0.1.0-r1_all.ipk
python3 scripts/make-ipk.py                   # 带完整 Depends，等同于 Makefile
```

OpenWrt 的 `.ipk` 是 **gzip 包裹的 tar**（`./debian-binary` + `control.tar.gz` +
`data.tar.gz`），不是 Debian 的 ar；脚本按此格式生成。`--minimal-deps` 只声明
`libc/python3/python3-readline/ip-full`，便于在没装齐可选包的路由器上冒烟测试。
正式发布仍建议走 SDK。

依赖见 [docs/DEPENDENCIES.md](docs/DEPENDENCIES.md)。默认依赖较多（约 52 MB），
小闪存设备请删掉 `Makefile` 中 `DEPENDS` 里用不到的行——缺包时对应功能输出
`... apply failed`，其余配置不受影响。

## 使用

```
root@OpenWrt:~# vyoscli
Welcome to vyoscli (a VyOS-style CLI for OpenWrt).
root@OpenWrt:~$ configure
root@OpenWrt# set system host-name edge-router
root@OpenWrt# set interfaces ethernet eth0 address 203.0.113.10/24
root@OpenWrt# set service dhcp-server shared-network-name LAN subnet 192.168.50.0/24 default-router 192.168.50.1
root@OpenWrt# show configuration
root@OpenWrt# compare
root@OpenWrt# commit
```

远程改 SSH/防火墙等敏感配置时用两段式提交：

```
root@OpenWrt# commit confirmed 5     # 5 分钟内不确认就自动回滚
root@edge-router# commit confirm     # 一切正常，取消定时器
```

命令不熟时按 `?`：

```
root@OpenWrt# set interfaces ethernet ?
  eth0  Per-interface config
  eth1  Per-interface config
root@OpenWrt# set firewall rule 900 ?
  dest-port  Destination port
  target     ACCEPT/DROP/REJECT
```

## 命令参考

完整清单（223 条，含每条命令的说明与示例）见 **[docs/COMMANDS.md](docs/COMMANDS.md)**，
由 `scripts/gen-command-reference.py` 从配置树自动生成。下面是最常用的部分。

### 操作模式

| 命令 | 作用 | 示例 |
|---|---|---|
| `configure` | 进入配置模式 | `configure` |
| `exit` / `quit` | 退出 CLI | `exit` |
| `show version` | 系统/内核/固件版本与硬件资产 | `show version` |
| `show dependencies` | 检查依赖包是否齐全 | `show dependencies` |
| `show interface` | 接口摘要（地址/MAC/MTU/状态） | `show interface` |
| `show interface ethernet <if>` | 单接口详情 | `show interface ethernet eth0` |
| `show history` | 本次会话的命令历史 | `show history` |
| `show log` | 系统日志（`logread`） | `show log` |
| `show configuration` | 运行配置树形视图 | `show configuration` |
| `show configuration commands` | 运行配置导出为 `set` 命令 | `show configuration commands` |
| `show configuration json` | 运行配置 JSON | `show configuration json` |
| `show system` | 系统状态摘要 | `show system` |
| `show system uptime` | 运行时长/负载 | `show system uptime` |
| `show system memory` | 内存占用 | `show system memory` |
| `show system storage` | 文件系统占用 | `show system storage` |
| `show system processes` | 进程列表 | `show system processes` |
| `show system kernel-messages` | 内核环缓冲 | `show system kernel-messages` |
| `show system login` | 本地用户账户 | `show system login` |
| `show system drift` | 上次 commit 后被改动/删除的 UCI 段 | `show system drift` |
| `show ip route` | 路由表 | `show ip route` |
| `show ip route static` | 静态路由 | `show ip route static` |
| `show ip route connected` | 直连路由 | `show ip route connected` |
| `show ip route summary` | 路由条数摘要 | `show ip route summary` |
| `show container` | 运行中的 podman 容器 | `show container` |
| `show container image` | 本地镜像 | `show container image` |
| `show dhcp lease` | DHCP 租约 | `show dhcp lease` |
| `show smartdns` | smartdns 状态 | `show smartdns` |
| `show hardware usb` | USB 设备 | `show hardware usb` |
| `ping <host>` | 调 busybox ping | `ping 1.1.1.1` |
| `add container image <img>` | 拉取镜像 | `add container image nginx:alpine` |
| `delete container image <img>` | 删除镜像 | `delete container image nginx:alpine` |
| `restart service <svc>` | 重启服务 | `restart service ssh` |
| `reload service <svc>` | 重载服务 | `reload service firewall` |

> op 模式下未知命令会透传给 shell（例如 `logread -f`、`nslookup`），
> 找不到命令时给出 `Invalid command` 与相近命令提示。

### 配置模式

| 命令 | 作用 | 示例 |
|---|---|---|
| `set <path> <value>` | 在 candidate 中写值（list 类型自动追加） | `set system host-name r1` |
| `delete <path> [value]` | 删除节点或 list 中的某一项 | `delete system name-server 8.8.8.8` |
| `edit <path>` / `next <path>` | 进入子节点，提示符带 `[path]` | `edit interfaces ethernet eth0` |
| `up` | 返回上一层 | `up` |
| `show configuration` | 查看 candidate（未提交会标注） | `show configuration` |
| `compare` | running 与 candidate 的差异 | `compare` |
| `commit` | 应用 candidate 并落盘 | `commit` |
| `commit confirmed [N]` | 应用并挂 N 分钟自动回滚（默认 5） | `commit confirmed 3` |
| `commit confirm` | 取消挂起的回滚定时器 | `commit confirm` |
| `discard` | 丢弃未提交修改 | `discard` |
| `save` | 立即持久化 running（commit 已自动写盘） | `save` |
| `sync` | 按 applied.json 只重放漂移的段落 | `sync` |
| `rollback [timestamp]` | 回滚到某个 commit 快照 | `rollback` |
| `exit` | 退回上一层 / 操作模式 | `exit` |

### 配置树速览

| 子树 | 常用命令示例 |
|---|---|
| `system` | `set system host-name r1`<br>`set system timezone Asia/Shanghai`<br>`set system ntp ntp.aliyun.com`<br>`set system login user admin authentication plaintext-password ***` |
| `interfaces ethernet` | `set interfaces ethernet eth0 address 192.0.2.10/24`<br>`set interfaces ethernet eth0 description uplink`<br>`set interfaces ethernet eth0 vif 100 address 192.0.2.100/24` |
| `interfaces bridge` | `set interfaces bridge br0 member eth1`<br>`set interfaces bridge br0 vlan 10 tagged eth1` |
| `interfaces wireguard` | `set interfaces wireguard wg0 address 10.99.0.1/24`<br>`set interfaces wireguard wg0 peer <pubkey> endpoint 1.2.3.4:51820` |
| `interfaces tunnel/vxlan/dummy/loopback` | `set interfaces tunnel tun0 encapsulation gre`<br>`set interfaces vxlan vx0 vni 42`<br>`set interfaces dummy dum0 address 10.10.10.1/32` |
| `protocols static` | `set protocols static route 10.0.0.0/8 next-hop 192.168.1.1` |
| `protocols bgp` | `set protocols bgp local-as 65001`<br>`set protocols bgp neighbor 10.0.0.2 remote-as 65002`<br>`set protocols bgp network 203.0.113.0/24` |
| `protocols route-map` | `set protocols route-map RM1 permit 10 set local-preference 200` |
| `policy` | `set policy community-list 10 rule 10 regex 65001:*`<br>`set policy route-redirect proxy rule 10 dport 80` |
| `vpn ipsec` | `set vpn ipsec ike-group G1 proposal 10 encryption aes256`<br>`set vpn ipsec site-to-site peer 203.0.113.5 secret ***` |
| `service ssh` | `set service ssh port 2222`<br>`set service ssh root-login true` |
| `service dhcp-server` | `set service dhcp-server shared-network-name LAN subnet 192.168.50.0/24 default-router 192.168.50.1` |
| `service dnsmasq/smartdns/adguard` | `set service dnsmasq port 53`<br>`set service smartdns server aliyun ip 223.5.5.5` |
| `service crontab` | `set service crontab backup schedule '0 3 * * *'`<br>`set service crontab backup script /etc/vyoscli/scripts/backup.sh` |
| `service sqm/tcp-accelerate` | `set service sqm interface eth0`<br>`set service tcp-accelerate congestion-control bbr` |
| `firewall` | `set firewall zone lan network lan`<br>`set firewall rule 100 dest-port 22 target ACCEPT` |
| `nat` | `set nat source rule 100 out-interface wan`<br>`set nat destination rule 10 port 8080 to 192.168.1.10` |
| `container` | `set container web image nginx:alpine`<br>`set container web port 8080:80` |
| `traffic-policy` | `set traffic-policy shaper wan interface eth0` |
| `vrf` | `set vrf name blue table 100` |

## 配置存储

| 路径 | 内容 |
|---|---|
| `/etc/vyoscli/running.json` | 当前生效配置（commit 成功后写入） |
| `/etc/vyoscli/candidate.json` | 未提交的修改（每条 set/delete 即时落盘） |
| `/etc/vyoscli/applied.json` | commit 写过的 UCI section 指纹（`show system drift` 用） |
| `/etc/vyoscli/history/<ts>.json` | 每次 commit 前的快照，保留 20 个 |
| `/etc/vyoscli/backup/network.<section>.json` | 接管某个已有接口前的原配置备份 |
| `/etc/vyoscli/rollback.conf` | 存在即表示有挂起的 confirmed-commit 定时器 |

配置文件为 `0600`（内含 WireGuard 私钥、PSK、密码等）。

开机时 `init.d/vyoscli` 会在后台执行一次 `vyoscli --sync`：与 UCI 一致时是空操作，
配置被恢复/手工改过时只重放漂移的段落。

## 测试

```bash
python3 -m unittest discover -s tests -v
```

- `tests/test_cli.py`：候选配置、编辑路径、渲染回放、commit/discard/rollback、补全与 `?`
- `tests/test_paths.py`：文档命令与命令树的可达性矩阵
- `tests/test_apply.py`：mock `uci`/`init.d`，断言 commit 生成的确切命令
- `tests/test_schema.py`：schema/template 的每条 spec 都可 set 且类型正确

命令树只改 `schema/config-tree.json`，然后：

```bash
python3 scripts/build-config-tree.py      # 生成 config_tree.py
python3 scripts/gen-command-reference.py  # 生成 docs/COMMANDS.md
```

`tests/test_tree_source.py` 会校验生成物与源一致。

### CI

`.github/workflows/ci.yml` 在每次 push / PR 上执行：

1. 全量单测；
2. `./scripts/check-generated.sh`——校验 `config_tree.py` 与 `docs/COMMANDS.md` 是否由源生成且无差异；
3. `python3 scripts/make-ipk.py --minimal-deps` 做一次无 SDK 的打包冒烟。

本地等价检查：

```bash
python3 -m unittest discover -s tests
./scripts/check-generated.sh
python3 scripts/make-ipk.py --minimal-deps
```

## 已知限制

完整清单见 [docs/AUDIT.md](docs/AUDIT.md)；与 VyOS 1.5 官方配置指南的逐项对比和补全优先级见 [docs/VYOS-GAP.md](docs/VYOS-GAP.md)。最需要注意的：

- 部分叶子（`description`/`mtu`/`mac`/`vif`/`vrf` 等）目前只写入 JSON，尚未下发；
- IPsec 的 remote-access/证书模式、wireless（需射频硬件）未做端到端验证；
- commit 不是原子操作：某一段下发失败时其余段仍会执行，并返回成功；
- VyOS 风格防火墙（`firewall ipv4/ipv6 ...`）渲染到 `inet vyos_fw`（priority -10）：它可以提前 drop/reject，`accept` 仍会继续走 OpenWrt fw4 的 zone 策略；
- VyOS 风格 NAT（`nat source/destination rule`）渲染到 `inet vyos_nat`（dstnat-10/srcnat-10），会先于 fw4 的 zone masquerade 生效；
- `service https` 提供只读 API，目前是明文 HTTP + Bearer token（TLS 待 PKI 完成后接入），建议只监听回环或内网；
- 动态节点在嵌套层级（如 `wireguard … peer`）只给 `<name>` 提示，不列现有实例。

后续规划见 [docs/AUDIT.md](docs/AUDIT.md) 的“建议的演进方案”。
