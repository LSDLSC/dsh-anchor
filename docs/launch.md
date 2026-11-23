# 发布文案与渠道清单

> 目标：让「在做 AI 长期记忆的人」搜得到、看得懂、装得上。文案可整段复制。

---

## 一句话（中英）

- 中文：**给陪伴型 AI 的记忆锚**——分层记事实、可恢复的遗忘墓地、纯标准库零依赖，2C4G 跑得动。
- English: **A memory anchor for companion AI** — layered facts, a recoverable forgetting graveyard, zero dependencies, runs on a 2C4G box.

## 三句话版

1. 你的 agent 换会话就失忆，靠三样东西救：事实库、人格锚、遗忘机制。
2. 这个仓库把它们做成一个目录 + 几个脚本：`facts.jsonl` 记事实，`soul.md` 守人格，`graveyard/` 存删掉但还能捞回来的东西。
3. 没有数据库、没有守护进程、没有网络调用；目录拷走就是备份。

---

## 小红书 / 即刻（短帖）

标题：**我给我的 AI 造了个「墓地」，它会忘东西，但忘掉的东西都还在**

正文：
发现一个反直觉的事：让 AI 记住更多，效果不一定更好；有时是「该忘的没忘」。

所以我给它做了个记忆锚：
- 事实分层存（每轮常驻的规则 / 可检索的事实 / 按天的经历 / 交接状态）
- 遗忘用 ACT-R 激活值，不删，只是越用越热、不用变冷
- 不想再被想起的，移进 `graveyard/`，不销毁，`restore` 随时捞回来
- 人格层 `soul.md` 不进遗忘，永远先加载

纯标准库，零依赖，2 核 4G 就能跑。开源了：github.com/LSDLSC/dsh-anchor

#AI #Agent #大模型 #记忆 #开源 #GitHub

---

## 知乎（回答/文章开头）

**问题：如何给 AI Agent 做长期记忆？**

先说结论：大多数方案把「存」做完了，把「忘」和「丢」没做完。我们的落法是三层——事实（facts）、经历（journal）、人格（soul），加一个物理墓地（graveyard）。

配一段 30 行的最小实现思路 + 仓库地址。核心取舍：不用向量库（2C4G 跑不动）、不搞硬删（数据丢了就真没了）、遗忘用激活值不用阈值（没有硬性过期）。

---

## V2EX / 技术群（一句话 + 链接）

给 AI 做的记忆锚：分层记忆 + 可恢复遗忘 + 零依赖，2C4G 可跑。反面的教训是：会话注册表被第二个进程覆盖、记忆只剩一份、人设被时间冲淡。都写成了工具。https://github.com/LSDLSC/dsh-anchor

---

## Hacker News

Title: `Show HN: Anchor – layered long-term memory for AI agents with a recoverable graveyard`

Text:
I kept hitting the same failures with agent memory: a second host process overwrote the session registry, the only copy of memory went stale, and the persona drifted. Anchor is a small, dependency-free toolkit that treats reliability first: facts/episodes/persona stored as plain files, ACT-R style activation for recall (no hard expiry), and a graveyard where forgotten items are moved instead of deleted — `restore` brings them back.

Runs on a 2C4G box. DSH is the first adapter; the core is host-agnostic (JSON-file adapter included).
Repo: https://github.com/LSDLSC/dsh-anchor

---

## Reddit r/LocalLLaMA

Title: `Anchor: a zero-dependency memory layer for local agents (facts/episodes/persona + recoverable forgetting)`

Body: (same as HN, plus) Zero deps means no sentence-transformers/Chroma needed; retrieval is keyword + activation scoring, which is deliberate for small boxes. Looking for feedback on the forgetting parameters.

---

## 发布前检查清单

- [x] README 中英文（`README.md` / `README.en.md`）
- [x] GitHub topics（agent-memory、long-term-memory、forgetting、act-r、dsh…）
- [ ] GitHub Release v0.1.0（tag 已推，网页点一下 Release 填 notes）
- [ ] 中文社区：小红书 / 知乎 / V2EX / 即刻
- [ ] 英文社区：HN Show HN / Reddit r/LocalLLaMA
- [ ] awesome 列表 PR（awesome-dsh-plugin 等，需你自己的 GitHub 账号）
- [ ] 星标引导：README 开头加「如果它帮到你，点个 star」

## 谁需要它（目标人群）

1. 自己做角色扮演 / 陪伴型 agent 的人（LocalLLaMA、SillyTavern 圈）
2. 用 DSH / Claude Code / Cursor 之类跑长期任务、被上下文挤爆的人
3. 想在 2C4G 小机器上跑 agent、不想引向量库的人
4. 学生/个人开发者——需要一个「能读懂全部源码」的记忆实现
