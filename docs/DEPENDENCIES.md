# 依赖说明

vyoscli 本身是纯 Python（约 200 KB），但各子系统真正下发时需要对应的 OpenWrt 包。
**不要自动安装依赖**：commit 过程中做网络 IO 既慢又不可控，尤其在改 WAN 时容易失联。
推荐流程：先安装需要的包，再进 CLI 配置。

## 依赖检查

```bash
show dependencies              # 按功能列出 OK/MISSING
show dependencies bgp          # 只看某个功能
show dependencies mtr
```

输出示例：

```
Feature      Package                        Status
-----------  -----------------------------  --------
mtr          mtr                           OK
bgp          frr                           OK
bgp          frr-ospfd                     OK
container    podman                        OK
container    iptables-nft                  MISSING

Install missing packages with:
  opkg install iptables-nft ...
```

检查规则：

1. 优先查 `opkg list-installed`；
2. 包名不同但二进制已存在时视为可用（例如 `dnsmasq-full` 提供 `dnsmasq`、
   `mtr-json` 提供 `mtr`）；
3. 只提示，不自动安装。

## 核心依赖（必须）

| 包 | 用途 |
|---|---|
| `python3` | 运行时 |
| `python3-readline` | Tab 补全、历史 |
| `ip-full` | `ip route/rule` 高级参数 |

对应 `--minimal-deps` 打包形态。

## 功能依赖（按需）

| 功能 | 包 |
|---|---|
| BGP / OSPF / RIP / BFD | `frr`、`frr-ospfd`、`frr-ripd`、`frr-bfdd` |
| WireGuard | `kmod-wireguard`、`wireguard-tools` |
| OpenVPN | `openvpn-openssl` |
| IPsec | `strongswan-ipsec`、`strongswan-charon`、`strongswan-mod-aes`、`strongswan-mod-sha2` |
| L2TP | `xl2tpd`、`ppp-mod-pppol2tp` |
| 容器 | `podman`、`netavark`、`iptables-nft`、`ip6tables-nft`、`kmod-ipt-nat`、`iptables-mod-nat-extra`、`kmod-ipt-conntrack`、`iptables-mod-conntrack-extra`、`kmod-ipt-extra`、`iptables-mod-extra` |
| LLDP | `lldpd` |
| MTR | `mtr` |
| DNS | `dnsmasq`（通常已装） |
| smartdns | `smartdns` |
| AdGuard | `adguardhome` |
| SQM | `sqm-scripts`、`tc` |
| SNMP | `snmpd` |
| 串口服务器 | `conserver` |
| 用户管理 | `shadow-useradd`、`shadow-chpasswd` |
| 隧道 | `kmod-gre`、`kmod-ipip`、`kmod-vxlan` |
| TCP 加速 | `kmod-tcp-bbr`、`kmod-tcp-hybla` |
| dummy 接口 | `kmod-dummy` |

## 打包策略

### 方案 A：核心包 + 按需安装（推荐）

`vyoscli` 只依赖 `python3/python3-readline/ip-full`，用户按功能 `opkg install`。
优点是体积小、升级不牵动数据库/FRR；缺点是首次配置某功能要手动装包。
`show dependencies` 和 commit 的 `... apply failed` 都会给出提示。

### 方案 B：核心包 + 全功能 meta 包

```makefile
Package/vyoscli
  DEPENDS:=+python3 +python3-readline +ip-full

Package/vyoscli-full
  DEPENDS:=vyoscli +frr +frr-ospfd +frr-ripd +frr-bfdd \
           +wireguard-tools +kmod-wireguard +openvpn-openssl \
           +strongswan-ipsec +strongswan-charon \
           +strongswan-mod-aes +strongswan-mod-sha2 \
           +xl2tpd +podman +lldpd +mtr \
           +smartdns +adguardhome +sqm-scripts +snmpd +conserver \
           +kmod-gre +kmod-ipip +kmod-vxlan +kmod-dummy
```

`vyoscli-full` 的 `install` 段为空，仅作为依赖集合。适合“一次装齐”的固件。

### 方案 C：按功能拆 meta 包

```makefile
Package/vyoscli-bgp
  DEPENDS:=vyoscli +frr +frr-ospfd +frr-ripd +frr-bfdd

Package/vyoscli-vpn
  DEPENDS:=vyoscli +wireguard-tools +kmod-wireguard \
           +openvpn-openssl +strongswan-ipsec +strongswan-charon \
           +xl2tpd

Package/vyoscli-container
  DEPENDS:=vyoscli +podman +iptables-nft +ip6tables-nft \
           +kmod-ipt-nat +iptables-mod-nat-extra \
           +kmod-ipt-conntrack +iptables-mod-conntrack-extra
```

适合镜像仓库/批量部署。当前仓库的 `Makefile` 仍是全量 `DEPENDS`，
发布时可根据固件大小选择上面任一方案。

## 缺包时的行为

所有 `_apply_*` 尽力而为：缺命令/配置时把错误写入该段 note，其余配置继续。
例如：

```
Commit complete.
  - lldp apply failed: Command '['uci', 'set', 'lldpd.config=config']' ...
  - bgp apply failed: ... 
```

处理顺序：

1. `show dependencies <feature>` 找缺失包；
2. `opkg install ...`；
3. 重新 `commit`（或 `sync`）让该段重放。

## 维护

功能依赖清单在 `package/vyoscli/files/usr/lib/vyoscli/op_show.py` 的
`FEATURE_DEPS`；新增功能时同步更新本文件、`Makefile` 和 `show dependencies`。
