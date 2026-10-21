# vyoscli — 类 VyOS 的 OpenWrt CLI

> 本项目由 **豆包 (Doubao)** 辅助编写。

一个用 Python 写的、VyOS 风格的命令行接口，作为 OpenWrt 原生 `opkg` 包编译安装。
保留 VyOS 的核心交互模型：**操作模式 / 配置模式**分离、**候选配置 (candidate) → commit → running** 三段式事务、Tab 补全。

## 目录结构

```
package/vyoscli/
├── Makefile                          # OpenWrt 包定义（opkg）
└── files/
    ├── usr/
    │   ├── bin/vyoscli               # shell 启动器
    │   └── lib/vyoscli/              # Python 包本体
    │       ├── __init__.py
    │       ├── __main__.py           # python -m vyoscli 入口
    │       ├── cli.py                # REPL、双模式、命令分发
    │       ├── tree.py               # 命令树节点 + 动态参数节点
    │       ├── config.py             # running/candidate 双层 JSON 配置库
    │       └── commands.py           # 内置命令注册
    └── etc/
        ├── init.d/vyoscli            # procd 启动脚本
        └── vyoscli/                  # 运行时生成 running.json / candidate.json
```

## 编译到 OpenWrt

1. 把整个 `package/vyoscli/` 目录拷进你的 OpenWrt SDK 源码树：
   ```bash
   cp -r package/vyoscli <openwrt_sdk>/package/utils/
   ```
2. 进入 SDK 根目录，选包：
   ```bash
   make menuconfig
   # Utilities  --->  <M> vyoscli
   ```
3. 编译：
   ```bash
   make package/vyoscli/compile V=s -j$(nproc)
   ```
4. 产出 ipk 在：
   ```
   bin/packages/<arch>/base/vyoscli_0.1.0-1_all.ipk
   ```
5. 装到路由器：
   ```bash
   scp bin/packages/<arch>/base/vyoscli_0.1.0-1_all.ipk root@router:/tmp/
   ssh root@router 'opkg install /tmp/vyoscli_0.1.0-1_all.ipk'
   ```

依赖：`python3` + `python3-readline`（Makefile 里已声明，opkg 会自动拉）。

## 使用

登录路由器后执行：

```
root@OpenWrt:~# vyoscli
Welcome to vyoscli (a VyOS-style CLI for OpenWrt). Type 'exit' to quit.
root@OpenWrt:~$ configure
root@OpenWrt# set system host-name edge-router
root@OpenWrt# set interfaces ethernet eth0 address 203.0.113.10/24
root@OpenWrt# set interfaces ethernet eth0 description Uplink
root@OpenWrt# show configuration
root@OpenWrt# commit
Commit complete. Configuration applied to running system.
root@edge-router# save
Saved to /etc/vyoscli/running.json
root@edge-router# exit
root@edge-router:~$ show interface
```

## 命令一览

| 模式 | 命令 | 作用 |
|---|---|---|
| op | `configure` | 进入配置模式 |
| op | `show version` | 显示系统/版本信息 |
| op | `show interface` | 接口摘要（来自 running 配置） |
| op | `show system` | 打印当前 running 配置 |
| op | `ping <host>` | 调 busybox ping |
| cfg | `set <path> <value>` | 在 candidate 里写值（list 类型自动追加） |
| cfg | `delete <path> [value]` | 删除节点或 list 中某一项 |
| cfg | `edit <path>` / `next <path>` | 进入子节点，提示符带路径 |
| cfg | `up` | 上一层 |
| cfg | `show configuration` | 打印 candidate（未提交会标注） |
| cfg | `commit` | candidate → running，落盘 running.json |
| cfg | `discard` | 丢弃未提交修改 |
| cfg | `save` | 持久化 running.json |
| cfg | `exit` | 退出当前层；在顶层则退回操作模式 |

## 配置存储

- `/etc/vyoscli/running.json` — 当前运行配置（commit 时写入，开机加载）。
- `/etc/vyoscli/candidate.json` — 未提交的修改（重启 CLI 后仍保留）。
- `/etc/vyoscli/history/<timestamp>.json` — 每次 commit 前的快照，保留最近 20 个。
- `/etc/vyoscli/rollback.conf` — 存在即表示有挂起的 auto-rollback 定时器。

## 两条工程规则

1. **底层下发优先级**：OpenWrt 有 UCI 对应功能的，一律走 `uci` + `reload <service>`（网络、hostname、DNS、防火墙、DHCP……）；没有 UCI 对应功能的，才直接用 Linux 命令（`ip route`、`sysctl`、`nft`……）。
2. **配置版本化 + 定时回滚**：每次 commit 前打时间戳快照；远程改配置用 `commit confirmed <分钟>`，超时不 confirm 就自动回滚，防止把自己锁在门外。

## commit confirmed（远程运维防自杀）

```
configure
set interfaces ethernet eth1 address 192.168.5.1/24
commit confirmed 5          # 5 分钟内不 confirm 就回滚
# 假设改完你 SSH 断了，5 分钟后设备自动恢复原配置，你能重新连回来
# 如果一切正常，重新登录后：
configure
commit confirm              # 取消定时器，永久生效
```

状态机：

```
candidate 有修改
   │
   ├── commit                → 立即生效，无定时器（老行为）
   ├── commit confirmed [N]  → 生效 + 挂 N 分钟定时器（默认 5）
   │                              ├── N 内 commit confirm → 定时器取消，永久生效
   │                              └── N 超时 → 自动 rollback 到 commit 前快照
   └── rollback [timestamp]  → 手动回滚到指定快照（默认最近一次）
```

## 新增命令

| 命令 | 作用 |
|---|---|
| `commit` | 立即生效，不挂定时器 |
| `commit confirmed [minutes]` | 生效并挂自动回滚定时器（默认 5 分钟） |
| `commit confirm` | 取消挂起的定时器 |
| `rollback [timestamp]` | 回滚到指定快照；不带时间戳回滚到最近一次 |
| `show history` | 列出所有快照时间戳 |

## 已接入 UCI 下发的配置

| VyOS 路径 | UCI 落点 | reload |
|---|---|---|
| `interfaces ethernet <x> address <ip/pfx>` | `network.<section>.ipaddr` | `/etc/init.d/network reload` |
| `system host-name <name>` | `system.@system[0].hostname` | `uci apply` |
| `system name-server <ip>` | `dhcp.@dnsmasq[0].server` | (下次 dnsmasq 重启生效) |

未接入 UCI 的（仅存 JSON，留待扩展）：`interfaces ethernet <x> description`。



## 扩展新命令

在 `commands.py` 的 `build_tree()` 里加一行即可，例如加 NTP：

```python
sys_named.add(Node(name="ntp", help="NTP server",
                   value_type="ipv4", action=_cfg_noop))
```

然后在 `config.py` 的 `DEFAULT_RUNNING` 里加上对应字段。真正下发到 netifd/UCI 的逻辑目前留了 `TODO` 钩子（`config.py:commit()`），按你的硬件环境补就行。

## 本地开发（Windows/macOS/Linux）

不依赖 OpenWrt 也能跑：

```powershell
$env:PYTHONPATH = "C:\Users\taylorg\Documents\OpenWrt\package\vyoscli\files\usr\lib"
$env:VYOSCLI_ETC = "$env:TEMP\vyoscli-etc"
python -m vyoscli
```

冒烟脚本：`python smoke_test.py` / `python smoke_test2.py`。
