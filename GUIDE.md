# vyoscli 配置指南

类 VyOS 的 OpenWrt CLI。目录结构对齐 [VyOS 1.5 官方文档](https://docs.vyos.io/en/1.5/configuration/index.html)。

## 目录

- [入门](#入门)
- [System](#system)
- [Interfaces](#interfaces)
- [Protocols](#protocols)
- [VPN](#vpn)
- [Service](#service)
- [Firewall](#firewall)
- [NAT](#nat)
- [VPN](#vpn)
- [Container](#container)
- [Traffic Policy](#traffic-policy)
- [运维](#运维)

---

## 入门

```
root@OpenWrt:~$ configure
root@OpenWrt# set ...
root@OpenWrt# commit
root@OpenWrt# exit
```

远程改 SSH/firewall/VPN 必用：

```
root@OpenWrt# commit confirmed 3
root@OpenWrt:~$ commit confirm
```

---

## System

### Hostname

```
set system host-name router-gz
commit
```

### Timezone / NTP

```
set system timezone Asia/Shanghai
set system ntp server ntp.aliyun.com
commit
```

### DNS

```
# 路由器自身 resolver
set system dns 223.5.5.5

# dnsmasq 上游（客户端用）
set system name-server 223.5.5.5
commit
```

### Login User

本地用户管理。

```
set system login user admin full-name "Administrator"
set system login user admin authentication plaintext-password mypass123
commit
```

SSH 公钥：

```
set system login user admin authentication public-keys laptop key "AAAAB3NzaC1yc2E..."
set system login user admin authentication public-keys laptop type ssh-rsa
commit
```

禁用账号：

```
set system login user admin disable
commit
```
### Hardware asset

```
set system hardware vendor "Custom"
set system hardware model "x86-2L"
set system hardware serial "E1X16225005023060077"
commit
```

---

## Interfaces

### Ethernet

```
set interfaces ethernet eth0 description WAN
set interfaces ethernet eth0 address dhcp

set interfaces ethernet eth1 description LAN
set interfaces ethernet eth1 address 192.168.1.1/24
set interfaces ethernet eth1 address 192.168.2.1/24
commit
```

### Interface role

```
set interfaces ethernet eth0 role wan
set interfaces ethernet eth1 role lan
commit
```

### Wireless

```
set interfaces wireless wlan0 mode ap
set interfaces wireless wlan0 ssid "MyWiFi"
set interfaces wireless wlan0 security wpa2
set interfaces wireless wlan0 key "password123"
commit
```

### Bridge

```
set interfaces bridge br0 member eth1
set interfaces bridge br0 address 192.168.1.1/24
commit
```

### Dummy

```
set interfaces dummy dum0 address 10.255.0.1/32
commit
```

### Tunnel (GRE / IPIP)

```
set interfaces tunnel tun0 mode gre
set interfaces tunnel tun0 local-ip 1.1.1.1
set interfaces tunnel tun0 remote-ip 2.2.2.2
set interfaces tunnel tun0 address 10.0.0.1/30
commit
```

### VXLAN

```
set interfaces vxlan vxlan0 vni 100
set interfaces vxlan vxlan0 remote 239.1.1.1
set interfaces vxlan vxlan0 address 192.168.100.1/24
commit
```

---

## Protocols

### Static route

```
# 普通路由
set protocols static route 0.0.0.0/0 next-hop 192.168.1.1

# 黑洞（静默丢弃）
set protocols static route 192.168.99.0/24 blackhole

# 拒绝（ICMP unreachable）
set protocols static route 10.99.0.0/16 reject

commit
```

查看：show ip route

### BGP

```
set protocols bgp local-as 65001
set protocols bgp router-id 192.168.1.1

set protocols bgp neighbor 10.0.0.2 remote-as 65002
set protocols bgp neighbor 10.0.0.2 description "ISP-A"

set protocols bgp network 192.168.1.0/24
commit
```

---

## Service

### SSH

```
set service ssh port 22
set service ssh root-login true
commit

# 关闭
set service ssh disable
commit

# 恢复
delete service ssh disable
commit
```

### DHCP

```
set service dhcp br0 start 192.168.1.100
set service dhcp br0 end 192.168.1.200
set service dhcp br0 lease 12h
set service dhcp br0 gateway 192.168.1.1
set service dhcp br0 dns 192.168.1.1
commit
```

查看租约：`show dhcp lease`

### DNS Forwarding

基于 dnsmasq 的 DNS 转发器。

#### 上游 DNS

```
# 全局上游
set service dnsmasq name-server 223.5.5.5
set service dnsmasq name-server 8.8.8.8

# 按域名转发（split-horizon）
set service dnsmasq domain internal.corp name-server 10.0.0.1
commit
```

#### 监听地址和端口

```
set service dnsmasq listen-address 192.168.1.1
set service dnsmasq port 53
commit
```

#### 允许查询的客户端

```
set service dnsmasq allow-from 192.168.1.0/24
commit
```

#### 缓存

```
set service dnsmasq cache-size 10000
set service dnsmasq negative-ttl 3600
commit
```

#### DNSSEC

```
set service dnsmasq dnssec validate
# 可选：off | process-no-validate | process | log-fail | validate
commit
```

### SmartDNS

高性能 DNS 转发，支持按域名测速选最快上游。

```
set service smartdns enabled true
set service smartdns port 5333
set service smartdns listen-address 127.0.0.1
set service smartdns forbid-aaaa true

set service smartdns server aliyun ip 223.5.5.5
set service smartdns server google ip 8.8.8.8

# 域名列表文件
set service smartdns domain-rules-file /etc/vyoscli/lists/domains.txt
commit
```

### AdGuardHome

带广告过滤的 DNS。

```
set service adguard enabled true
set service adguard port 53
set service adguard listen-address 127.0.0.1
set service adguard web-port 3000
commit
```

Web UI：`http://<router-ip>:3000`

### DNS 冲突保护

commit 时自动检测 dnsmasq/smartdns/adguard 的 IP:端口冲突，冲突直接拒掉。

### Console Server

串口控制台服务器，远程管理多台设备。基于 conserver + dropbear 多实例。

#### USB 驱动

```
opkg update
opkg list-installed *usb-serial*
opkg list *usb-serial*

# 按芯片装驱动
opkg install kmod-usb-serial-pl2303    # Prolific PL2303
opkg install kmod-usb-serial-ftdi      # FTDI FT232/FT4232
```

查看设备：

```
show hardware usb
lsusb
ls -lsh /dev/ttyUSB*
```

#### 配置

```
set service console-server device usb0 description "core-sw-1"
set service console-server device usb0 speed 115200
set service console-server device usb0 data-bits 8
set service console-server device usb0 parity none
set service console-server device usb0 stop-bits 1
set service console-server device usb0 ssh-port 2201
commit
```

#### commit 后

1. 自动 `opkg install conserver`
2. 写 `/etc/conserver/conserver.cf`
3. 起 conserver 服务
4. 每个串口起一个 dropbear 实例：
   ```
   /usr/sbin/dropbear -j -k -r /etc/dropbear/dropbear_rsa_host_key \
     -c 'console usb0' -P /var/run/vyoscli-console-usb0.pid -p 2201
   ```

#### 远程访问

```
ssh root@<router-ip> -p 2201
```

#### 快捷键

- `Ctrl+E c ?` 帮助
- `Ctrl+E c .` 断开
- `Ctrl+E c f` 强制接管
- `Ctrl+E c b` 广播消息

#### 强制下线占用会话

```
show console-server ports
fuser -k /dev/ttyUSB0
```

#### 本地串口工具

```
# picocom
opkg install picocom
picocom -b 115200 /dev/ttyUSB0    # Ctrl+A Ctrl+X 退出

# screen
opkg install screen
screen -S console /dev/ttyUSB0 115200   # Ctrl+A D 退出
screen -ls
screen -r <pid>
```
### Crontab

```
set service crontab update-domains schedule "0 3 * * *"
set service crontab update-domains command /etc/vyoscli/scripts/update-domains.sh
commit
```
## VPN

### IPsec Site-to-Site

基于 strongswan 的站点间 VPN。

#### Phase 1 (IKE)

```
set vpn ipsec ike-group IKE lifetime 28800
set vpn ipsec ike-group IKE proposal 10 encryption aes256
set vpn ipsec ike-group IKE proposal 10 hash sha256
set vpn ipsec ike-group IKE proposal 10 dh-group 14
```

#### Phase 2 (ESP)

```
set vpn ipsec esp-group ESP lifetime 3600
set vpn ipsec esp-group ESP proposal 10 encryption aes256
set vpn ipsec esp-group ESP proposal 10 hash sha256
```

#### Peer

```
set vpn ipsec site-to-site peer 10.0.2.2 local-address 10.0.1.2
set vpn ipsec site-to-site peer 10.0.2.2 remote-address 10.0.2.2
set vpn ipsec site-to-site peer 10.0.2.2 local-id 10.0.1.2
set vpn ipsec site-to-site peer 10.0.2.2 remote-id 10.0.2.2
set vpn ipsec site-to-site peer 10.0.2.2 secret mysecret
set vpn ipsec site-to-site peer 10.0.2.2 ike-group IKE
set vpn ipsec site-to-site peer 10.0.2.2 esp-group ESP
set vpn ipsec site-to-site peer 10.0.2.2 tunnel 0 local-prefix 192.168.1.0/24
set vpn ipsec site-to-site peer 10.0.2.2 tunnel 0 remote-prefix 192.168.2.0/24
commit
```

#### commit 后

1. 自动 `opkg install strongswan-minimal`
2. 写 `/etc/ipsec.conf` + `/etc/ipsec.secrets`
3. `/etc/init.d/ipsec restart`

#### 查看

```
show ipsec sa
```
---

## Firewall

### Zone

```
set firewall zone lan network br0
set firewall zone lan input ACCEPT
set firewall zone lan output ACCEPT
set firewall zone lan forward ACCEPT

set firewall zone wan network eth0
set firewall zone wan input DROP
set firewall zone wan output ACCEPT
set firewall zone wan forward DROP
commit
```

### Forwarding

```
set firewall forwarding lan-wan src lan
set firewall forwarding lan-wan dest wan
commit
```

### Rule

```
set firewall rule 10 name "allow-ssh"
set firewall rule 10 src wan
set firewall rule 10 dest-port 22
set firewall rule 10 target ACCEPT
commit
```

---

## NAT

### Source NAT

```
set nat source rule 10 out-interface wan
set nat source rule 10 translation masquerade
commit
```

### Destination NAT

```
set nat destination rule 20 in-interface wan
set nat destination rule 20 port 80
set nat destination rule 20 to 192.168.1.10
commit
```

---

### WireGuard

```
set interfaces wireguard wg0 address 10.0.10.1/24
set interfaces wireguard wg0 private-key "xxxxbase64xxxx"
set interfaces wireguard wg0 listen-port 51820

set interfaces wireguard wg0 peer abcpublickey allowed-ips 10.0.10.2/32
set interfaces wireguard wg0 peer abcpublickey endpoint 1.2.3.4:51820
commit
```

### OpenVPN

```
set interfaces openvpn vtun0 mode tun
set interfaces openvpn vtun0 config-file /etc/vyoscli/openvpn/client.ovpn
commit
```

---

## Container

基于 Podman 的容器引擎。

### 镜像 Image

```
# 指定镜像
set container nginx image nginx:alpine

# 指定仓库 registry
set container nginx image quay.io/nginx:alpine
commit
```

### 网络 Network

```
# 加入已有 podman 网络
set container nginx network podman

# 静态 IP
set container nginx network podman address 10.89.0.10
commit
```

### 端口映射 Port

```
# 主机 8080 -> 容器 80
set container nginx port 8080:80
commit
```

### 卷挂载 Volume

```
# 配置文件挂载（只读）
set container nginx volume /etc/nginx/conf.d:/etc/nginx/conf.d:ro
commit
```

### 环境变量 Environment

```
set container mysql environment MYSQL_ROOT_PASSWORD value 'secret'
set container mysql environment MYSQL_DATABASE value 'appdb'
commit
```

### 重启策略 Restart

```
set container nginx restart always
# 可选：always | on-failure | no
commit
```

### 资源限制 Resource

```
set container nginx memory 256
set container nginx cpu-quota 0.5
commit
```

### 禁用 Disable

```
set container nginx disable
commit
```

### 操作命令 Operations

```
show container                       # 运行中容器
show container image                 # 本地镜像
add container image nginx:alpine    # pull
delete container image nginx:alpine # rmi
restart container nginx             # 重启
```

### 完整示例 Example

```
set container mysql image mysql:8.0
set container mysql network podman
set container mysql environment MYSQL_ROOT_PASSWORD value 'rootpwd'
set container mysql environment MYSQL_DATABASE value 'appdb'
set container mysql restart always

set container nginx image nginx:alpine
set container nginx network podman
set container nginx port 8080:80
set container nginx restart always
commit
```

---

## Traffic Policy

route-map：

```
set protocols route-map FROM-ISP permit 10 set local-preference 200
set protocols route-map FROM-ISP permit 10 set med 50
set protocols route-map FROM-ISP permit 10 set community 65001:100
set protocols bgp neighbor 10.0.0.2 route-map-in FROM-ISP
commit
```

---

## 运维

```
show version
show interface
show configuration
show configuration commands
show system
show ip route
show container
show dhcp lease

restart service ssh
reload service firewall
```

备份：

```
tar czf /tmp/vyoscli.tgz -C /etc vyoscli/
```
