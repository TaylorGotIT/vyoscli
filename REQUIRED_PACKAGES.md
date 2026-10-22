# vyoscli 依赖策略

## 全部硬依赖（装 vyoscli 必装，15 个包）

| 包 | 大小 | 用途 |
|---|---|---|
| python3 | ~5 MB | 运行时 |
| python3-readline | ~0.5 MB | Tab 补全 |
| ip-full | ~0.5 MB | `show ip route` / `ss` |
| smartdns | ~0.5 MB | DNS 策略 |
| adguardhome | ~10 MB | 广告过滤 DNS |
| frr | ~5 MB | BGP 动态路由 |
| kmod-tcp-bbr | ~0.1 MB | BBR 拥塞控制 |
| kmod-tcp-hybla | ~0.1 MB | Hybla 拥塞控制 |
| kcptun | ~2 MB | KCP 加速隧道 |
| kmod-wireguard | ~0.5 MB | WireGuard VPN |
| wireguard-tools | ~0.5 MB | WireGuard 工具 |
| openvpn-openssl | ~2 MB | OpenVPN |
| strongswan | ~3 MB | IPsec VPN |
| conserver | ~0.5 MB | 串口服务器 |
| podman | ~20 MB | 容器 |
| podman-plugins | ~5 MB | 容器插件 |
| **总共约 56 MB** | | |

## 说明

- 装 vyoscli 时全部依赖自动安装
- 适合闪存 128 MB 以上的路由器
- 如果设备闪存紧张，可以删掉 Makefile DEPENDS 里不需要的包，改成按需安装
