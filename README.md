# Anchor · 陪伴型 AI 的记忆锚

> 让 AI 记住该记的，忘掉该忘的，丢了还能捞回来。

Anchor 是一套从真实故障里长出来的工具集：会话注册表被覆盖、记忆只剩一份、人设被时间冲淡、旧内容挤占上下文。它不是"又一个记忆插件"，而是把**可靠性**当成第一需求来做——先不丢，再谈聪明。

**两个核心**：跨会话的长期记忆库（分层的 facts / journal / soul），和一片物理的遗忘墓地
（移入不销毁、可 `restore`、不进检索）。这是这个仓库最想分享的部分——我们也是从别人的
ACT-R、MemoryOS、YourMemory 里学来的，只是把它们拼成了能跑在 2C4G 小机器上的样子。

纯 Python / Node 标准库，零依赖。DSH 是第一个适配器，不是唯一目标。

---

## 事故：我的 AI 把会话列表清空了三次

### 第一次
DSH 的会话列表不扫描 `sessions/` 目录，只认 `~/.dsh/storages/workspace.json` 里的 `sessionIds`。我搬过工作区，注册表里少了六条，UI 里就只剩最近的三条——文件都在，只是没人登记。

### 第二次
补登记之后，列表自己退回去了。根因是同时跑了两个宿主实例，每个实例在内存里各持一份清单，退出时把旧清单整体写回注册表。**一次覆盖，六条会话消失。**

### 第三次
注册表里的 `updatedAt` 变成了毫秒数字（`1794152228979`），新版 schema 只接受 ISO 字符串。整个 workspace 域加载失败，列表空白，日志里只有一行 `expected string, received number`。

三次事故的共同点：**数据都在，坏的是"登记"和"格式"**。修法也不是加功能，是加守卫：

- 会话注册表守卫：`updatedAt` 数字转 ISO，磁盘有、注册表没有的会话补登记，写完重启宿主生效。
- 三副本同步：本地 → 裸仓 → GitHub，任一份失败都显式报错，不静默。
- 记忆分层：常驻人格 / 事实 / 原文 / 交接分开存，单层损坏不牵连全局。

---

## 三个包

| 目录 | 是什么 | 给谁 |
|---|---|---|
| `quickstart/` | 一条命令装最小可用集（记忆目录 + 工具脚本 + 可选 timer） | 想先跑起来、不想读文档的人 |
| `deploy/` | 完整部署条件包：systemd 单元、同步脚本、配置样例 | 要 7×24 跑在服务器上的人 |
| `src/` | 开发源文件：记忆、激活、忘墓、守卫、沉淀 | 想改、想接进自己 agent 的人 |

三个包共用同一套源码，`quickstart` 和 `deploy` 只是不同的使用姿势。

---

## 换一个 agent？适配器层

核心（注册表守卫、记忆库、墓地、激活）不依赖 DSH。DSH 只是第一个适配器：

| 适配器 | 需要什么 | 给谁 |
|---|---|---|
| `dsh`（默认） | DSH 的 `workspace.json` + `sessions/` | 用 DSH 的人 |
| `jsonfile` | 任意 JSON 注册表 + 磁盘目录 | 其他 agent / 自研系统 |

自研系统只要满足两条就能用同一个守卫：

1. 注册表是 JSON，里面有个字符串数组存已登记的 id；
2. 磁盘上一个目录里，每个子目录（或文件）代表一个真实存在的 id。

```bash
# 例子：任何"JSON 里有 sessions 列表 + sessions/ 目录"的系统
ANCHOR_REGISTRY=/srv/app/registry.json \
ANCHOR_REGISTRY_IDS=state.sessions \
ANCHOR_REGISTRY_DIR=/srv/app/data/sessions \
python3 src/registry_guard.py --adapter jsonfile
```

写自己的适配器：实现 `load / registered / disk_ids / merge / save` 五个方法
（协议见 `src/adapters/base.py`）。记忆层（facts / journal / graveyard / activation）
本来就和 agent 无关，只认目录。

---

## 设计要点

### 1. 记忆分四层，别混在一起
- **hot**：常驻判断规则，每轮注入
- **facts**：可检索的事实条目（JSONL，一行一条）
- **journal**：会话原文摘要，按天落盘
- **soul**：人格锚点，不进遗忘机制

分层的好处是：清理只动该动的层，人设和事实不会被"顺手优化"。

### 2. 遗忘用 ACT-R，不用阈值表
条目激活：

```
B = ln( Σ_j (t_j + 1)^(-0.5) )      # t_j = 第 j 次访问距今小时
A = B + 0.4 × importance + ε         # ε ~ N(0, 0.5)
P = σ(A − τ)                         # 召回概率
```

- 没有"30 天自动删除"这种硬边界，只有概率高低；
- 噪声项让旧条目偶尔"突然想起来"；
- `importance` 让身份、规矩类条目不沉底；
- 检索即复习：命中一次，`access_times` 追加一次，下次更热。

### 3. 删除分三级，墓碑先行
- 降权：只是概率变低，可逆
- 移入墓地：物理保留、退出检索，`restore` 随时捞回
- 焚毁：清墓地 + 备份，需要明确确认

绝大多数"该忘"的东西停在第二级就够。


### 4. 反馈层：任务跑没跑、跑成没有，一条命令回答
每个任务执行后写结构化结果（`state/anchor/<task>.json`），`anchor status` 只读结果、不解析日志：

```
$ anchor status
  [OK ] 注册表守卫    正常     最后 2026-11-20 16:12:37（0 分钟前）
        本次有变更：补登记 2 个会话
  [NEW ] 会话沉淀     从未运行   最后 从未（—）
  [LATE] 三副本同步    超期     最后 2026-11-20 09:00:00（7 小时前）
```

失败、超期、从未运行都会标出来，退出码非 0，可以挂到任何监控上。

---

## 快速开始

```bash
git clone <this-repo> && cd anchor
./quickstart/install.sh            # 装脚本 + 建目录
./quickstart/install.sh --with-timers   # 额外装 systemd timer（需 root）
```

装完试：

```bash
python3 src/anchor.py status      # 所有任务状态
python3 src/anchor.py check       # 环境/路径/依赖自检
python3 src/anchor.py guard       # 手动跑一次守卫

memory add "用户偏好先给结论" --tags 偏好 --importance 4
memory search 结论
activation score
```

## 已知缺陷

这个仓库是从真实故障里长出来的，不是成熟产品。诚实的缺陷清单见
[`docs/limitations.md`](docs/limitations.md)：锁防不了宿主进程、定时检查有窗口期、
Windows 无锁、与 DSH 版本强绑定、参数是经验值、没有自动化测试和 CI。

欢迎提 Issue 或 PR，尤其是能复现"双宿主覆盖"的测试用例、跨平台适配和参数实证建议。

## 引用与致谢

- ACT-R 基础激活与逻辑斯蒂召回：`engram-ai` / `mtrace` / `CerebroCortex-RS`
- 记忆强度衰减函数：`YourMemory`（sachitrafa）
- 分层与巩固：`MemoryOS`（BAI-LAB，EMNLP 2025）
- 时间衰减 + 事件修正：`minecraft-ai-companion`（Tempura）
- 遗忘曲线：`MemoryBank`（AAAI 2024）

## License

MIT
