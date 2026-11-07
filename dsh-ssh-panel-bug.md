# DSH SSH 面板：主机密钥变更后“忘记主机指纹”不生效，需重启应用

## 环境

- DSH 桌面端（Windows，Web GUI `http://127.0.0.1:59187`）
- 右侧 SSH 面板连接目标：ImmortalWrt 23.05.2 x86_64（VM，RAM/initramfs 启动）
- 目标每次重启会重新生成 dropbear host key

## 复现步骤

1. 通过 SSH 面板首次连接目标，指纹被缓存。
2. 目标重启（host key 重新生成）。
3. 面板重连，提示：

   ```
   Host key for 192.168.75.206:22 changed ...
   Expected SHA256:NLM98DL4CZXf1gVW1VYUSVWUdkjOut+ygtoeZTPCX0g=
   presented SHA256:t6NKe8ccH7AIZ3XTct+hg1WoiPekLBRGeaRaiYDEsLk=
   ... use "忘记主机指纹" and reconnect
   ```

4. 点击“忘记主机指纹”并重连：仍然报同一个旧指纹错误。
5. 同一时间用系统 `ssh` 连接：`ssh-keygen -R 192.168.75.206` 后可正常登录，证明新 key 正常、网络正常。
6. 重启 DSH 桌面端后，面板连接恢复正常。

## 实际行为

- “忘记主机指纹”没有真正删除插件侧的缓存条目；只有重启应用才生效。
- 插件使用的是独立指纹库，不是系统 `~/.ssh/known_hosts`：

  `C:\Users\taylorg\.dsh\storages\ssh_ops_known_hosts.json`

  复现时该文件中仍是旧指纹：

  ```json
  "192.168.75.206:22": {
    "fingerprint": "NLM98DL4CZXf1gVW1VYUSVWUdkjOut+ygtoeZTPCX0g="
  }
  ```

- 手动把该文件更新为新指纹并重启应用后，连接恢复。

## 期望行为

1. 检测到 host key 变更时，面板应展示“旧指纹 / 新指纹”，并提供“信任新指纹并连接”按钮；点击后立即更新 `ssh_ops_known_hosts.json` 并连接，无需重启应用。
2. “忘记主机指纹”应删除该 host 的缓存条目（文件和内存同时），随后重连按首次连接处理。
3. 建议增加连接级设置：`strictHostKeyChecking = yes | accept-new | no`，方便实验室/会重装的环境。
4. 指纹缓存应在每次连接前从存储重新读取，避免应用启动时的内存副本覆盖用户操作。

## 影响

- 主机重装/重刷/OpenWrt RAM 启动场景下，面板无法连接，必须改 JSON 或重启应用。
- 系统 `ssh` 正常，容易让用户误以为是网络或服务端问题。

## 临时规避

1. 更新 `C:\Users\taylorg\.dsh\storages\ssh_ops_known_hosts.json` 中对应 host 的 `fingerprint`，或删除该条目。
2. 或重启 DSH 桌面端。
3. 系统 CMD 侧可 `ssh-keygen -R <host>`。

## 备注

- 面板提示文案中的 “忘记主机指纹” 与实际问题不符：点击后并未清除持久化缓存。
- 目标为 RAM 启动的 OpenWrt，host key 每次重启都会变化，因此该问题可稳定复现。
