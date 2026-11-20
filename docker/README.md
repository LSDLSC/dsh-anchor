# Docker 安装

不想装 Python/Node，就只装 Docker。

## 一条命令

```bash
# 看状态
docker run --rm \
  -v ~/.dsh:/data/dsh \
  -v ./memory:/data/memory \
  anchor:local status
```

## 构建

```bash
git clone <repo> && cd anchor
docker build -f docker/Dockerfile -t anchor:local .
```

## compose

```bash
DSH_HOME=~/.dsh MEMORY_DIR=./memory docker compose -f docker/docker-compose.yml up --build
```

## 为什么挂载两个目录

| 挂载 | 用途 |
|---|---|
| `~/.dsh` → `/data/dsh` | 读写 `storages/workspace.json`、`sessions/`（守卫需要写） |
| `./memory` → `/data/memory` | 记忆库（facts/journal/graveyard/soul） |

守卫会写 `workspace.json`，所以第一个挂载不能是只读。
只想看状态、不改任何东西时，可以加 `:ro`。

## 注意

- 镜像里没有 systemd，定时任务要在宿主机上配（`deploy/systemd/`），或者在容器里用
  `sleep` + `while` 循环简单跑。
- 守卫重启宿主（`RESTART_CMD`）在容器里没有意义，设成空字符串即可。
