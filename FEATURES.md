# vyoscli 功能清单

类 VyOS 的 OpenWrt CLI，opkg 包 `vyoscli`。

## 交互模型

| 特性 | 说明 |
|---|---|
| 双模式 | op `root@host:~$` / config `root@host#` |
| candidate 配置 | 改配置不立即生效，存 candidate.json |
| commit | candidate → running，自动打快照（保留 20 个） |
| commit confirmed N | 生效但挂 N 分钟定时器，超时自动回滚 |
| commit confirm | 取消挂起的定时器 |
| rollback [ts] | 手动回滚到任意历史快照 |
| discard | 丢弃未提交修改 |
| Tab 补全 | 两列对齐：命令名 + help 描述 |

## op 模式

| 命令 | 作用 |
|---|---|
| `configure` | 进入配置模式 |
| `exit` / `quit` | 退出 CLI |
| `show version` | 版本/内核/架构/硬件资产卡 |
| `show interface` | 接口 IP 摘要（多 IP 换行） |
| `show configuration` | running 配置树形缩进 |
| `show configuration commands` | running 配置为 `set ...` 脚本 |
| `show configuration json` | running 配置为 JSON |
| `show system` | uptime/cpu/memory/storage/processes/kernel-messages/login |
| `show ip route` / `static` / `connected` / `summary` | 路由表 |
| `show container` | podman 容器列表 |
| `show container image` | podman 镜像列表 |
| `show dhcp lease` | dnsmasq DHCP 租约 |
| `show smartdns` | smartdns 状态 |
| `add container image <name>` | podman pull |
| `delete container image <name>` | podman rmi |

## 配置树

```
set system
  host-name <text>
  timezone <IANA tz>                e.g. Asia/Shanghai
  ntp server <host>
  language <locale>
  name-server <ipv4>                dnsmasq 上游
  dns <ipv4>                        路由器自身 resolver
  hardware vendor/model/serial

set interfaces ethernet <ifname>
  address <ipv4/pfx>                (可重复)
  description <text>
  role <lan|wan>

set interfaces wireless <ifname>
  mode <ap|sta>
  ssid <text>
  channel <num>
  security <wpa2|wpa3|none>
  key <text>

set interfaces bridge br0
  member <ifname>
  address <ipv4/pfx>

set interfaces dummy dum0
  address <ipv4/pfx>

set interfaces tunnel tun0
  mode <gre|ipip>
  local-ip <ipv4>
  remote-ip <ipv4>
  address <ipv4/pfx>

set interfaces vxlan vxlan0
  vni <num>
  remote <ipv4>

set interfaces wireguard wg0
  address <ipv4/pfx>
  private-key <key>
  listen-port <port>
  peer <pubkey>
    allowed-ips <cidr>
    endpoint <ip:port>

set interfaces openvpn vtun0
  mode <tun>
  config-file <path>

set protocols static route <prefix>
  next-hop <ipv4>

set protocols bgp
  local-as <asn>
  router-id <ipv4>
  network <cidr>                    (可重复)
  neighbor <ipv4>
    remote-as <asn>
    description <text>
    route-map-in <name>
    route-map-out <name>

set protocols route-map <name> permit <num>
  set local-preference <n>
  set med <n>
  set community <asn:nn>
  set next-hop <ipv4>

set service ssh
  port <port>
  root-login <true|false>

set service dhcp <ifname>
  start <ipv4>
  end <ipv4>
  lease <time>
  gateway <ipv4>
  dns <ipv4>                        (可重复)

set service smartdns
  enabled <true|false>
  port <port>
  listen-address <ipv4>
  forbid-aaaa <true|false>
  server <name> ip <ipv4>
  domain-rules-file <path>

set service adguard
  enabled <true|false>
  port <port>
  listen-address <ipv4>
  web-port <port>

set service dnsmasq
  port <port>
  listen-address <ipv4>

set service crontab <name>
  schedule "<cron>"
  command <path>

set firewall zone <name>
  network <net>
  input/output/forward ACCEPT|DROP|REJECT

set firewall forwarding <name>
  src <zone>
  dest <zone>

set firewall rule <num>
  name <text>
  src <zone>
  dest-port <port>
  target ACCEPT|DROP|REJECT

set nat source rule <num>
  out-interface <if>
  translation masquerade

set nat destination rule <num>
  in-interface <if>
  port <port>
  to <internal-ipv4>

set container <name>
  image <image>
  network <net>
  port <host:container>             (可重复)
  volume <host:container>           (可重复)
  restart <always|on-failure|no>
  command <text>
  environment <KEY> value <text>
```

## 底层下发

| 配置 | 下发方式 | reload |
|---|---|---|
| interfaces ethernet/bridge/dummy | UCI network.* | netifd reload |
| interfaces wireless | UCI wireless.vyos_* | wifi reload |
| interfaces tunnel/vxlan | UCI interface.vyos_* | netifd reload |
| interfaces wireguard | UCI network/network.wg0 | wg-quick up |
| interfaces openvpn | /etc/openvpn/*.conf | openvpn init restart |
| system host-name/timezone/ntp | UCI system.* | sysntpd restart |
| system name-server | UCI dhcp.@dnsmasq[0].server | dnsmasq reload |
| system dns | /tmp/resolv.conf.d/resolv.conf.head | - |
| protocols static route | UCI network.vyos_route_* | netifd reload |
| protocols bgp | UCI frr.vyos_bgp_* + frr.conf 标记块 | restart（核心变）/ vtysh 热加载（route-map） |
| service ssh | UCI dropbear.* | dropbear restart |
| service dhcp | UCI dhcp.vyos_* | dnsmasq reload |
| service dnsmasq | UCI dhcp.@dnsmasq[0].port/listenaddress | dnsmasq restart |
| service smartdns | UCI smartdns.vyos_* | smartdns restart |
| service adguard | UCI adguardhome.main | adguardhome restart |
| service crontab | /etc/crontabs/root（标记块） | cron restart |
| firewall | UCI firewall.vyos_* | firewall reload |
| nat | UCI firewall.vyos_nat_* | firewall reload |
| container | podman rm -f / podman run | - |

## DNS 端口冲突检测

commit 前自动检测：
- dnsmasq / smartdns / adguard 都纳入 candidates
- 按 IP:端口粒度判定（`ss -tulnp`）
- 0.0.0.0 通配监听会和任何同端口冲突
- 冲突直接拒绝 commit，running 回滚到旧值

## 按需安装（commit 时才 opkg install）

| 包 | 触发条件 |
|---|---|
| smartdns | set service smartdns enabled true |
| adguardhome | set service adguard enabled true |
| podman / podman-plugins | set container ... |
| frr | set protocols bgp local-as |
| kmod-wireguard / wireguard-tools | set interfaces wireguard |
| openvpn-openssl | set interfaces openvpn |

硬依赖仅 python3 + python3-readline + ip-full（~6 MB）。

## 目录布局

```
/etc/vyoscli/
├── running.json         当前运行配置
├── candidate.json       未提交修改
├── rollback.conf        挂起的回滚定时器
├── history/             commit 快照（保留 20 个）
├── scripts/             用户脚本（cron 调用）
├── lists/               域名列表等数据文件
└── adguard/             AdGuardHome 持久化配置
```

迁移：`tar czf /tmp/vyoscli.tgz -C /etc vyoscli/`，新设备解包后 commit。
