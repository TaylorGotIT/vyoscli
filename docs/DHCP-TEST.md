# DHCP 测试模板

> 适用：vyoscli 的 `service dhcp-server`（后端写 dnsmasq/UCI）。
> `interface` 要填 **UCI 网络名**（`lan`/`wan`/`dum0`），不是设备名（`br-lan`/`eth1`）。
> 测试前备份：`cp /etc/config/dhcp /tmp/dhcp.bak`。
> 远程 SSH 操作建议用 `commit confirmed 5`，确认后再 `commit confirm`。

## 场景 A：隔离配置检查（dummy 接口）

只验证服务器配置、地址池、静态绑定和 `show` 输出；dummy 接口会丢弃报文，**不能**用它做 DHCP 客户端拿租约。

```sh
opkg install kmod-dummy     # 一次即可

configure

set interfaces dummy dum0 address 10.99.0.1/24
set service dhcp-server shared-network-name TEST interface dum0
set service dhcp-server shared-network-name TEST subnet 10.99.0.0/24 default-router 10.99.0.1
set service dhcp-server shared-network-name TEST subnet 10.99.0.0/24 name-server 10.99.0.1
set service dhcp-server shared-network-name TEST subnet 10.99.0.0/24 lease 600
set service dhcp-server shared-network-name TEST subnet 10.99.0.0/24 range R1 start 10.99.0.100
set service dhcp-server shared-network-name TEST subnet 10.99.0.0/24 range R1 stop 10.99.0.150
set service dhcp-server shared-network-name TEST subnet 10.99.0.0/24 static-mapping printer ip-address 10.99.0.50
set service dhcp-server shared-network-name TEST subnet 10.99.0.0/24 static-mapping printer mac-address aa:bb:cc:dd:ee:ff

commit
```

验证：

```sh
show dhcp server
show dhcp server pools
show dhcp server static
show dhcp server leases
uci show dhcp | grep vyos_dhcp
netstat -lunp | grep ':67'
```

清理：

```sh
configure
delete service dhcp-server
delete interfaces dummy dum0
commit
uci -q delete dhcp.vyos_dhcp_TEST_10_99_0_0_24
uci -q delete dhcp.vyos_dhcp_host_TEST_printer
uci commit dhcp
/etc/init.d/dnsmasq restart
show system drift
```

## 场景 B：真实客户端测试（LAN）

用现有 LAN（UCI 名 `lan`，设备 `br-lan`）：

```sh
configure

set service dhcp-server shared-network-name LAN interface lan
set service dhcp-server shared-network-name LAN subnet 192.168.1.0/24 default-router 192.168.1.1
set service dhcp-server shared-network-name LAN subnet 192.168.1.0/24 name-server 192.168.1.1
set service dhcp-server shared-network-name LAN subnet 192.168.1.0/24 lease 3600
set service dhcp-server shared-network-name LAN subnet 192.168.1.0/24 range R1 start 192.168.1.100
set service dhcp-server shared-network-name LAN subnet 192.168.1.0/24 range R1 stop 192.168.1.150

commit confirmed 5
commit confirm
```

> 这会重写 dnsmasq 的 DHCP 段，和 OpenWrt 原有的 `dhcp.lan` 冲突。
> 测试前备份 `/etc/config/dhcp`，并确保有 console/第二通道。

客户端验证（另一台机器）：

```sh
# Linux
udhcpc -i eth0 -q -n
ip addr show eth0
ip route

# Windows
ipconfig /renew
ipconfig /all
```

服务端确认：

```sh
show dhcp server
show dhcp server leases
show dhcp server pools
```

期望：

- `pools` 的 `Used/Total` 随客户端数量变化
- `leases` 出现客户端 MAC、分配 IP、主机名
- `static` 出现预绑定 MAC/IP

## 快速检查清单

| 检查项 | 命令 |
|---|---|
| 服务是否运行 | `show dhcp server` |
| 地址池范围/使用率 | `show dhcp server pools` |
| 动态租约 | `show dhcp server leases` |
| 静态绑定 | `show dhcp server static` |
| dnsmasq 是否监听 67 | `netstat -lunp \| grep ':67'` |
| 配置回放 | `show configuration commands \| grep dhcp-server` |
| 漂移 | `show system drift` |

## 回滚

```sh
configure
delete service dhcp-server
commit
# 如改过 LAN 的原生 DHCP，恢复备份：
# cp /tmp/dhcp.bak /etc/config/dhcp && /etc/init.d/dnsmasq restart
```
