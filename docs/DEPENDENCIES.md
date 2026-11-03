# 依赖说明

vyoscli 本身是纯 Python（约 200 KB），但要让各子系统真正下发，需要对应的 OpenWrt 包。
**这些包不会在 commit 时自动安装**：一次性 `opkg install` 完再进 CLI，避免在管理面上
做网络 IO。

## 当前 Makefile 硬依赖（约 52 MB）

| 包 | 用途 | 是否可以不要 |
|---|---|---|
| `python3`、`python3-readline` | 运行时、Tab 补全 | 必需 |
| `ip-full` | `show ip route`、`ip` 高级参数 | 建议保留 |
| `smartdns` | DNS 分流/测速 | 不用可删 |
| `adguardhome` | 广告过滤 DNS | 不用可删（注意：UCI 只能开关服务，DNS/Web 端口在 `/etc/adguardhome.yaml`） |
| `frr` | BGP、route-map | 不用可删 |
| `kmod-tcp-bbr`、`kmod-tcp-hybla` | 拥塞控制 | 不用可删 |
| `kmod-wireguard`、`wireguard-tools` | WireGuard | 不用可删 |
| `openvpn-openssl` | OpenVPN | 不用可删 |
| `strongswan`（或 `strongswan-minimal`） | IPsec | 不用可删 |
| `conserver` | 串口服务器 | 不用可删 |
| `podman` | 容器 | 不用可删（体积最大） |
| `kmod-gre`、`kmod-ipip`、`kmod-vxlan` | 隧道 | 不用可删 |
| `tc`、`sqm-scripts` | QoS / SQM | 不用可删 |
| `kmod-dummy` | `set interfaces dummy` 需要内核 dummy 驱动 | 不用可删（本机验证时未安装，dummy 设备创建失败） |

## 建议的两种安装形态

```makefile
# 1) 核心包：只有 CLI 与接口/防火墙/静态路由/DHCP 等基础能力（约 6 MB）
Package/vyoscli
  DEPENDS:=+python3 +python3-readline +ip-full

# 2) 全功能 meta 包：构建完整功能所需的一切（依赖 128 MB+ flash）
Package/vyoscli-full
  DEPENDS:=vyoscli +smartdns +adguardhome +frr +wireguard-tools \
           +openvpn-openssl +strongswan-minimal +conserver +podman \
           +kmod-wireguard +kmod-gre +kmod-ipip +kmod-vxlan \
           +kmod-tcp-bbr +kmod-tcp-hybla +sqm-scripts
```

打包时注意包名以设备 `opkg list` 为准（例如 `strongswan-minimal` 在部分源里叫
`strongswan`，`sqm-scripts` 提供 `tc` 相关脚本）。

## 缺包时的行为

所有 `_apply_*` 都是"尽力而为"：缺少命令或 UCI 配置时会把错误写进该段 note，
其余配置照常下发。例如：

```
Commit complete.
  - smartdns apply failed: [Errno 2] No such file or directory: 'uci'
  - netifd reloaded
```

`show dependencies` 会逐项检查并给出缺失包与安装命令（清单在
`usr/lib/vyoscli/op_show.py`，修改依赖时记得同步）。
