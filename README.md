# vyoscli — 类 VyOS 的 OpenWrt CLI

用 Python 实现的 VyOS 风格命令行，以 opkg 包形式安装到 OpenWrt。
保留 VyOS 的核心交互模型：**操作模式 / 配置模式**分离、
**candidate → commit → running** 事务、Tab 补全、`commit confirmed` 自动回滚。

编译产物是纯 Python 包，不依赖 UCI 之外的任何框架；没有 UCI 对应项时
才退化为 `ip`/`nft`/`tc` 等原生命令。

## 目录结构

```
package/vyoscli/
├── Makefile                      # OpenWrt 包定义（opkg）
├── files/
│   ├── usr/bin/vyoscli           # shell 启动器
│   ├── usr/lib/vyoscli/          # Python 包
│   │   ├── cli.py                # REPL、双模式、补全、命令分发
│   │   ├── tree.py               # 命令树、动态节点、路径解析、值校验
│   │   ├── commands.py           # 命令树定义
│   │   ├── schema.py             # 声明式路径定义（逐步替代手写节点）
│   │   ├── config_tree.py         # 生成的完整配置树数据（353 节点）
│   │   ├── config.py             # 配置库、事务、UCI/原生下发
│   │   ├── op_show.py            # show * 实现
│   │   └── __main__.py           # 入口 + 回滚定时器子进程
│   └── etc/init.d/vyoscli        # boot 时准备配置目录
scripts/build-ipk.sh              # SDK 内一键编译（无 sudo / 无 menuconfig）
tests/                            # unittest 测试（跨平台，无第三方依赖）
docs/
├── GUIDE.md                      # 完整配置指南
├── DEPENDENCIES.md               # 依赖清单与体积
└── AUDIT.md                      # 代码审查、已知问题、重构路线
```

## 编译与安装

```bash
# 1. 准备 SDK（版本按目标固件选，纯 Python 包对目标架构不敏感，但 DEPENDS
#    会按该 SDK 的包清单解析，建议与固件版本一致）
wget https://downloads.openwrt.org/releases/24.10.0/targets/x86/64/openwrt-sdk-24.10.0-x86-64_gcc-13.3.0_musl.Linux-x86_64.tar.zst
tar -I zstd -xvf openwrt-sdk-24.10.0-*.tar.zst

# 2. 一键编译（无需 sudo / menuconfig）
SDK=~/openwrt-sdk-24.10.0-x86-64_gcc-13.3.0_musl.Linux-x86_64 \
    ./scripts/build-ipk.sh
```

脚本做三件事：把 `package/vyoscli` 复制进 SDK、在 `.config` 里勾选
`CONFIG_PACKAGE_vyoscli=y`、`make package/utils/vyoscli/compile`，最后打印 ipk 路径。
手工编译等价于：

```bash
cd openwrt-sdk-*/
mkdir -p package/utils && cp -r /path/to/repo/package/vyoscli package/utils/
make defconfig
sed -i 's/^# CONFIG_PACKAGE_vyoscli is not set/CONFIG_PACKAGE_vyoscli=y/' .config
make defconfig && make package/utils/vyoscli/compile V=s
find bin/packages -name 'vyoscli*.ipk'
```

```bash
scp bin/packages/*/base/vyoscli_*.ipk root@router:/tmp/
ssh root@router 'opkg install /tmp/vyoscli_*.ipk'
```

### 无 SDK 快速打包（仅用于设备测试）

vyoscli 是 `PKGARCH:=all` 的纯 Python 包，SDK 只负责打包、不编译任何代码。
临时验证时可以直接生成 ipk：

```bash
python3 scripts/make-ipk.py --minimal-deps    # -> dist/vyoscli_0.1.0-r1_all.ipk
python3 scripts/make-ipk.py                   # 带完整 Depends，等同于 Makefile
```

注意 OpenWrt 的 `.ipk` 不是 Debian 的 ar 格式，而是 **gzip 包裹的 tar**
（内含 `./debian-binary`、`./control.tar.gz`、`./data.tar.gz`）；脚本按这个格式生成，
`opkg install` 可直接安装。`--minimal-deps` 只声明 `libc/python3/python3-readline/ip-full`，
便于在没装齐可选包的路由器上做冒烟测试；正式发布仍建议走 SDK（`scripts/build-ipk.sh`）。

依赖见 [docs/DEPENDENCIES.md](docs/DEPENDENCIES.md)。默认依赖较多（约 52 MB），
小闪存设备请删除 `Makefile` 中 `DEPENDS` 里用不到的行——缺包时对应功能会输出
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

命令清单与各配置项示例见 [docs/GUIDE.md](docs/GUIDE.md)。

## 配置存储

| 路径 | 内容 |
|---|---|
| `/etc/vyoscli/running.json` | 当前生效配置（commit 成功后写入） |
| `/etc/vyoscli/candidate.json` | 未提交的修改（每条 set/delete 即时落盘） |
| `/etc/vyoscli/history/<ts>.json` | 每次 commit 前的快照，保留 20 个 |
| `/etc/vyoscli/applied.json` | 每次 commit 写过的 UCI section 指纹，用于 `show system drift` |

开机时 init.d/vyoscli 会在后台执行一次 yoscli --sync：配置与 UCI 一致时是空操作，配置被恢复/手工改过时只重放漂移的段落。
| `/etc/vyoscli/rollback.conf` | 存在即表示有挂起的 confirmed-commit 定时器 |

配置文件为 `0600`（内含 WireGuard 私钥、PSK、密码等）。

## 测试

```bash
python3 -m unittest discover -s tests -v
```

- `tests/test_cli.py`：候选配置、渲染回放、commit/discard/rollback、补全
- `tests/test_paths.py`：文档命令与命令树的可达性矩阵
- `tests/test_apply.py`：mock `uci`/`init.d`，断言 commit 生成的确切命令

测试不需要路由器，Linux/macOS/Windows 均可运行。

## 已知限制

`docs/AUDIT.md` 记录了完整清单。最需要注意的几点：

- 部分配置项（`description`/`mtu`/`mac`/`vif`/`vrf` 等）目前只写入 JSON，尚未下发；
- BGP/IPsec/WireGuard/wireless/conserver 的 UCI 下发尚未在真机验证；
- JSON 与 UCI 是两份状态，没有开机对账，手工改 UCI 后 `show configuration` 会与设备不一致；
- commit 不是原子操作：某一段下发失败时其余段仍会执行，并返回成功。

后续规划见 [docs/AUDIT.md](docs/AUDIT.md) 的"建议的演进方案"。
