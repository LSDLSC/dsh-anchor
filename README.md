# Anchor · 陪伴型 AI 的记忆锚

[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![Zero dependencies](https://img.shields.io/badge/dependencies-0-success.svg)](src/memory.py)

> 让 AI 记住该记的，忘掉该忘的，丢了还能捞回来。

English: [README.en.md](README.en.md) · 如果它帮到你，点个 star 让更多人搜到。

**给正在做长期记忆的自己 agent 的人**：一个目录 + 一个 `memory.py`，就能把「事实 / 经历 / 人格」分层记下来；不想记住的移进墓地，不销毁、不丢失、随时能捞回来。纯标准库，没有数据库、没有守护进程，2C4G 的小机器也跑得动。

Anchor 是一套从真实故障里长出来的工具集：会话注册表被覆盖、记忆只剩一份、人设被时间冲淡、旧内容挤占上下文。它不是"又一个记忆插件"，而是把**可靠性**当成第一需求来做——先不丢，再谈聪明。

**两个核心**：跨会话的长期记忆库（分层的 facts / journal / soul），和一片物理的遗忘墓地
（移入不销毁、可 `restore`、不进检索）。这是这个仓库最想分享的部分——我们也是从别人的
ACT-R、MemoryOS、YourMemory 里学来的，只是把它们拼成了能跑在 2C4G 小机器上的样子。

纯 Python / Node 标准库，零依赖。DSH 是第一个适配器，不是唯一目标。

---

## 60 秒理解

一个 agent 换会话就失忆，通常靠三样东西救：**事实库**（记得住）、**人格锚**（不会变）、
**遗忘机制**（不会越攒越乱）。这个仓库把这三样做成一个目录 + 几个脚本：

```
$MEMORY_DIR/
├── hot.md                  每轮都要注入的判断规则（L1 常驻）
├── facts.jsonl             一行一条的可检索事实（L2 事实）
├── journal/                会话原文摘要，按天落盘（L3 经历）
├── state.json              上一次做到哪、下一步做什么（L4 交接）
├── soul/soul.md            身份、关系、底线（不进遗忘，只能人工改）
├── emotion.json            情绪状态 + 关系刻度（按小时衰减，见下）
└── graveyard/              墓地：移出检索但物理保留，可 restore
    ├── index.json
    └── 2026-11/facts-2026-11.jsonl
```

四个命令就能用起来：

```bash
export MEMORY_DIR="$HOME/.dsh/memory"
python3 src/memory.py add "用户偏好先给结论" --tags 偏好 --importance 4
python3 src/memory.py search 结论
python3 src/memory.py handoff          # 拼出"开机该读的东西"：soul → hot → state → 命中事实
python3 src/memory.py bury --id <id>   # 不想再被想起来，但不想真删
```

没有数据库、没有守护进程、没有网络调用。**目录就是全部状态**，拷走就是备份。

---

## 目录结构

| 路径 | 是什么 | 给谁 |
|---|---|---|
| `src/` | 全部源码：记忆、激活、墓地、守卫、沉淀、总览页 | 想改、想接进自己 agent 的人 |
| `quickstart/` | 一条命令装最小可用集（记忆目录 + 脚本 + 可选 timer） | 想先跑起来、不想读文档的人 |
| `deploy/` | 完整部署包：systemd 单元、同步脚本、配置样例 | 要 7×24 跑在服务器上的人 |
| `docker/` | Dockerfile + compose（只读挂载记忆目录） | 不想碰 systemd 的人 |
| `templates/` | 人格层与墓地的目录骨架和示例 | 第一次建库的人 |
| `docs/` | 深度文档：记忆模型、遗忘、架构、已知缺陷、事故复盘 | 想理解"为什么这么设计"的人 |

`quickstart` 和 `deploy` 共用同一套 `src/`，只是安装姿势不同；三者都不是必需的——
只要 `src/memory.py` 一个文件，加上一个目录，就能开始写事实。

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

## 记忆模型（够用版）

完整版在 [`docs/memory-model.md`](docs/memory-model.md)，这里只放"不看文档也不会用错"的部分。

### 四层，按"该不该被清理"分，不按"重不重要"分

| 层 | 文件 | 谁写 | 会被清理吗 |
|---|---|---|---|
| L1 常驻 | `hot.md` | 人，随时 | 不会自动清理，可人工精简 |
| L2 事实 | `facts.jsonl` | `memory add` | 会降权、会进墓地 |
| L3 经历 | `journal/` | 沉淀任务 | 一般只归档 |
| L4 交接 | `state.json` | 人 / 任务 | 覆盖式更新 |
| 人格 | `soul/soul.md` | **只能人工** | **永不** |

### 一条事实长什么样

```json
{"id":"a1b2c3d4","ts":"2026-11-20 20:41","text":"用户偏好先给结论","tags":["偏好"],"importance":4,"access_times":["2026-11-20 20:41"]}
```

`importance` 1–5，不写就按标签推：身份/规矩/纪律/安全 = 5，偏好/环境/项目/工具 = 4，其余 3。
`access_times` 每次检索命中追加一次，决定这条记忆"有多热"。

### 遗忘：ACT-R 激活，不是到期删除

```
B = ln( Σ_j (t_j + 1)^(-0.5) )      # t_j = 第 j 次访问距今小时
A = B + 0.4 × importance + ε         # ε ~ N(0, 0.5)
P = σ(A − τ)                         # 召回概率，τ 默认 0
```

- 没有"30 天自动删除"这种硬边界，只有概率高低；
- 噪声项让旧条目偶尔"突然想起来"；
- `importance` 让身份、规矩类条目不沉底；
- 检索即复习：命中一次，`access_times` 追加一次，下次更热。

### 删除分三级，墓碑先行

| 级别 | 做法 | 可逆 | 什么时候用 |
|---|---|---|---|
| 1 降权 | 不写 `access_times`，自然沉底 | 是 | 默认，什么都不用做 |
| 2 墓地 | `memory bury`，移出检索、原文保留 | 是，`restore` 随时回来 | 明确"不想再被想起来"的旧事 |
| 3 焚毁 | 清墓地 + 清备份 | **否** | 只有敏感信息或本人明确要求，且需确认 |

绝大多数"该忘"的东西停在第二级。第 3 级是例外路径，不是常规操作。

### 人格层为什么不跟着遗忘

`soul.md` 是"这个 AI 是谁、跟谁是什么关系、底线在哪"。它不进墓地、不按激活值降权、
不随上下文压缩消失。代价是它不自动生长，所以规则写死两条：**改要有理由**（`CHANGELOG.md` 一行）、
**改要经本人同意**。骨架见 [`templates/soul/`](templates/soul/)。

---

## 情绪与关系刻度

记忆管"记得什么"，情绪管"此刻什么状态、跟你到什么程度"。它单独存在 `emotion.json`，
因为更新节奏不同：事实按天累积，情绪按小时衰减。

```bash
emotion show                 # 现算状态
emotion show --inject        # 一行可直接塞进 system prompt：
                             # [心情] 开心（强度 4.2/10）；对对方：熟悉（亲密 12/100，信任 8）；昨天之后就没聊过
emotion event --affinity 3 --trust 1 --note "被夸了"
emotion set --mood 低落 --intensity 6 --tau 1.0
emotion touch                # 只记"聊过天"，不动情绪
```

**强度是现算的，不是存下来的**：

```
I(t) = I0 × exp(−hours / (tau × 24)) + time_bonus(hour) + noise(15min 种子)
低于 0.5 回落到「平静」
```

每种情绪有自己的 `tau`（兴奋 0.25–0.6 天，疲惫/低落 1.0 天，平静 3.0 天），
所以"开心"退得快、"难过"留得久，不需要写一堆 if。

**事件分三档**：强度 ≥6 覆盖（并加 20–80 分钟冷却）；3–5.9 混合（旧情绪打折而不是清零）；
<3 轻推（±1，不重置时间轴）。负面事件乘 0.7 的乐观偏置，一句气话不该把关系刻度打穿。

**关系刻度** `affinity` / `trust` 各 0–100，分五段：陌生 / 熟悉(21) / 亲近(41) / 亲密(61) / 家人(81)。
最近 30 条事件留在 `relationship.events`，能回看是哪件事把刻度推上去的。

自动侧接一行就够：

```bash
echo "用户说：谢谢你，今天辛苦了" | python3 src/emotion_auto.py --inject
```

它按关键词表判正负与强度，转成一次 `emotion event`，只做轻推。

> 注入位置建议放在 system prompt 的**最后一段**。放最前面模型会把它当人设来演，
> 而不是当"此刻的状态"来体现。细节见 [`docs/emotion-model.md`](docs/emotion-model.md)。

情绪不进遗忘机制，也不写进 `facts.jsonl`——它一天变好几次，不该挤占事实检索。
"性格"属于 `soul/soul.md`（只能人工改），情绪是性格在某一刻的表现。

---

## 命令一览

| 命令 | 作用 |
|---|---|
| `memory add "文本" --tags a,b --importance N` | 写一条事实 |
| `memory search 关键词` | 检索事实（只读 L2，不扫墓地） |
| `memory handoff` | 拼开机上下文：soul → hot → state → 命中事实 |
| `memory stats` | 条目数、标签分布、墓地数量 |
| `memory bury --id <id> \| --query 关键词` | 移入墓地（物理保留、退出检索） |
| `memory restore --id <id>` | 从墓地捞回 |
| `memory graveyard` | 列出墓地条目 |
| `activation score` | 按召回概率给全部事实排序 |
| `activation tick --id <id>` | 手工记一次访问（复习） |
| `anchor status` | 各任务跑没跑、跑成没有（读结构化结果，不解析日志） |
| `anchor check` | 环境/路径/依赖自检 |
| `anchor guard` | 手动跑一次注册表守卫 |
| `registry_guard --adapter dsh\|jsonfile` | 只跑守卫 |
| `emotion show [--inject]` | 查看现算情绪 / 输出一行注入文本 |
| `emotion set --mood X --intensity N` | 设定情绪基准与衰减常数 |
| `emotion event --affinity N --trust N --note 文本` | 记一次影响关系的事件 |
| `emotion touch` / `emotion decay` | 记一次对话 / 把现算强度结算回基准 |
| `python3 src/emotion_auto.py --text 文本` | 从一段对话自动轻推情绪 |

`anchor status` 的四种状态：`[OK ]` 正常、`[NEW ]` 从未运行、`[LATE]` 超期、`[FAIL]` 失败；
后三种退出码非 0，可以挂到任何监控上。

---

## 配置（全是环境变量，没有配置文件）

| 变量 | 默认 | 说明 |
|---|---|---|
| `MEMORY_DIR` | `$DSH_HOME/memory` 或 `~/.dsh/memory` | 记忆库根目录。未设置时依次尝试 `WHALE_MEMORY_DIR`、脚本上一级目录（含 `facts.jsonl` 或 `hot.md` 时），最后才用默认值 |
| `WHALE_MEMORY_DIR` | — | 旧变量名，兼容保留 |
| `DSH_HOME` | `~/.dsh` | DSH 根目录，用来推默认 `MEMORY_DIR` |
| `ANCHOR_ADAPTER` | `dsh` | 守卫用哪个适配器 |
| `ANCHOR_REGISTRY` | DSH 的 `workspace.json` | 注册表文件路径 |
| `ANCHOR_REGISTRY_IDS` | `state.sessions[].id` 之类 | 注册表里存 id 列表的 JSON 路径 |
| `ANCHOR_REGISTRY_DIR` | DSH 的 `sessions/` | 磁盘目录，每个子目录 = 一个 id |
| `RESTART_CMD` | 无 | 守卫写完注册表后重启宿主的命令 |
| `ANCHOR_TARGET_NAME` | `对方` | 情绪注入文本里怎么称呼对方；也可以写进 `emotion.json` 的 `"target"` 字段，环境变量优先 |

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
ANCHOR_REGISTRY=/srv/app/registry.json \
ANCHOR_REGISTRY_IDS=state.sessions \
ANCHOR_REGISTRY_DIR=/srv/app/data/sessions \
python3 src/registry_guard.py --adapter jsonfile
```

写自己的适配器：实现 `load / registered / disk_ids / merge / save` 五个方法
（协议见 `src/adapters/base.py`）。记忆层（facts / journal / graveyard / activation）
本来就和 agent 无关，只认目录。

---

## 安装

### 方式一：一条命令（推荐）

```bash
git clone https://github.com/LSDLSC/dsh-anchor.git && cd dsh-anchor
./quickstart/install.sh                    # 建目录 + 装脚本到 ~/.local/bin
./quickstart/install.sh --with-timers      # 额外装 systemd timer（需 root）
```

### 方式二：只要记忆，不要宿主集成

```bash
mkdir -p ~/.dsh/memory
cp src/memory.py src/activation.py ~/.dsh/memory/../  # 放哪都行，能 import 即可
export MEMORY_DIR=~/.dsh/memory
python3 src/memory.py add "第一条事实" --tags 示例
```

### 方式三：systemd（7×24 跑在服务器上）

`deploy/systemd/` 里有五组单元：`dsh-memory-sync`（三副本同步）、`dsh-memory-guard`（注册表守卫）、
`dsh-memory-digest`（会话沉淀）、`dsh-anchor-sync`（每小时比对仓库与线上脚本，只检测不覆盖），
以及对应 `.timer`。复制到 `/etc/systemd/system/`，改 `deploy/configs/example.env` 后 `systemctl enable --now`。

### 方式四：Docker

```bash
docker compose -f docker/docker-compose.yml up -d
```

容器里只挂记忆目录，不挂宿主数据；记忆文件的所有者是宿主用户，容器以只读方式看它。

---

## 这个仓库是自包含的

刻意做成"拷一个目录就能跑"：

- **没有私有依赖**：只用 Python 3 标准库（`memory.py`/`activation.py`/`anchor.py`/`registry_guard.py`）
  和 Node 标准库（`memory_digest.mjs`）。
- **没有必读文档**：本 README 里已经写全了目录结构、数据格式、CLI、环境变量、记忆与遗忘规则。
  `docs/` 是加深理解用的，不看也能正确使用。
- **没有外部服务**：不连数据库、不连向量库、不连模型 API。检索是纯文本匹配 + 激活值排序。
- **数据格式是纯文本**：`facts.jsonl` 一行一条、`journal/` 是 markdown、`state.json` 是普通 JSON，
  任何编辑器都能看，任何语言都能读。
- **可以整体搬走**：`tar czf memory.tgz $MEMORY_DIR` 就是完整备份，换机器解开即用。

如果哪天这个仓库被删了，你手上的记忆目录依然完整可用——这是有意为之。

---

## 隐私与脱敏

这个仓库是公开的，任何人都能 clone、下载、逐行读。所以它里面**不含任何真实数据**：

- 没有真实记忆：`*.jsonl`（事实与墓地）、`memory/`、`state/`、`emotion.json` 由 `.gitignore` 排除，仓库里只有空目录和示例；
- 没有本机信息：路径统一写成 `/home/user`、`/srv/app`，不含用户名、主机名、内网 IP、服务器地址；
- 没有凭据：密钥、令牌、密码、AccessKey 一律不出现；`memory_digest.mjs` 里带的是**打码规则**（`/LTAI[A-Za-z0-9]{10,}/` → `LTAI***` 之类），不是凭据本身；
- 没有真名：示例人格、示例事实都是占位文本，`templates/soul/soul.example.md` 只讲该写什么、不该写什么。

要公开发布自己的分支前，建议自己再扫一遍：

```bash
git log -p --all | grep -nE "你的用户名|你的主机名|你的内网IP|密码|token|LTAI|sk-" 
grep -rIn -E "/home/[a-z]+|/root/|[A-Z]:\\\\Users" . --exclude-dir=.git
```

记忆数据本身永远只该待在 `$MEMORY_DIR` 里，进版本库的只有代码和模板。

---

## 可视化

```bash
python3 src/memory_view.py --out ~/memory-view.html
```

生成一个单文件 HTML：常驻层、交接、事实（可搜索）、经历、墓地各一屏，只读，不联网。

---

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
