# 完整部署条件包

目标是"服务器上长期跑"：

| 组件 | 作用 |
|---|---|
| `systemd/dsh-memory-guard.{service,timer}` | 每小时修会话注册表（updatedAt / 补登记） |
| `systemd/dsh-memory-digest.{service,timer}` | 每天 23:50 把会话抽成 journal |
| `systemd/dsh-memory-sync.{service,timer}` | 每 10 分钟三副本同步 |
| `systemd/dsh-anchor-sync.{service,timer}` | 每小时比对仓库与线上记忆脚本（只检测，不覆盖） |
| `scripts/dsh-memory-sync.sh` | 同步脚本（本地 → 裸仓 → GitHub，失败显式报错） |
| `scripts/dsh-anchor-sync.sh` | 比对脚本（结果写 `$DSH_HOME/state/anchor/anchor-sync.json`） |
| `configs/example.env` | 路径与远端配置样例 |

## 部署顺序

1. 装 `deploy/scripts/dsh-memory-sync.sh` 和 `deploy/scripts/dsh-anchor-sync.sh` 到 `/usr/local/bin/`
2. 改 `systemd/*.service` 里的 `DSH_HOME` / `MEMORY_DIR` / `ANCHOR_REPO` 路径
3. `systemctl daemon-reload`
4. `systemctl enable --now dsh-memory-guard.timer dsh-memory-digest.timer dsh-memory-sync.timer dsh-anchor-sync.timer`
5. 验证：`journalctl -u dsh-memory-guard -n 20`；`anchor status` 里应多出「脚本一致性」一项

## 前置条件

- Linux + systemd（Windows 用任务计划程序，见 docs/architecture.md）
- Python 3.10+（守卫、记忆脚本）
- Node 18+（沉淀脚本）
- git（三副本）
