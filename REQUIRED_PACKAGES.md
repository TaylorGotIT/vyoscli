# vyoscli 依赖策略

## 硬依赖（装 vyoscli 必装）

| 包 | 大小 | 用途 |
|---|---|---|
| python3 | ~5 MB | 运行时 |
| python3-readline | ~0.5 MB | Tab 补全 |
| ip-full | ~0.5 MB | `show ip route` |

**总共约 6 MB**，即使 16 MB 闪存的路由器也能装。

## 按需自动安装（commit 时才装）

写了对应配置才触发 `opkg install`，没用到就不占空间。

| 包 | 触发条件 | 大小 |
|---|---|---|
| smartdns | `set service smartdns ...` commit | ~0.5 MB |
| podman | `set container ...` commit | ~20 MB |
| podman-plugins | `set container ...` commit | ~5 MB |

## 工作流程示例

```
# 全新安装 vyoscli，只有 6 MB 基础包
opkg install vyoscli.ipk

# 你只用基本 CLI，不碰 smartdns/container → 永远不会装 podman

# 哪天想用 DNS 策略
set service smartdns server cf ip 1.1.1.1
commit
# 输出：
#   installing optional package: smartdns ...
#     -> smartdns installed
#   smartdns reloaded

# 哪天想跑容器
set container nginx image nginx:alpine
commit
# 输出：
#   installing optional package: podman ...
#   installing optional package: podman-plugins ...
#     -> podman installed
#   started container nginx
```

## 前提

路由器要能联网（或本地有 opkg 源），第一次 commit 触发安装时会下载。如果设备离线，commit 会提示 install FAILED 但不破坏现有配置。
