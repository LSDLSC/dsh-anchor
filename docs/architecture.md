# 架构

## 组件关系

```
┌────────────── DSH 宿主 ──────────────┐
│  会话列表 ← storages/workspace.json   │
└──────────────┬───────────────────────┘
               │ 每 1h 检查
        workspace_guard.py ──► 修 updatedAt / 补 sessionIds ──► 重启宿主
               │
               │ 每 23:50
        memory_digest.mjs ──► memory/journal/*.md
               │
               │ 每 10min
        dsh-memory-sync.sh ──► 本地仓 → 裸仓 → GitHub

        memory.py       四层记忆 + 检索 + 墓地
        activation.py   ACT-R 激活打分
        emotion.py      情绪状态机
```

## 记忆分层

| 层 | 文件 | 生命周期 | 是否进遗忘 |
|---|---|---|---|
| hot（人格规则） | `hot.md` | 常驻 | 否 |
| facts（事实） | `facts.jsonl` | 可增可删 | 是（激活衰减） |
| journal（原文摘要） | `journal/YYYY-MM-DD-*.md` | 按天 | 是（概率降低） |
| soul（锚点） | `soul/soul.md` | 永不 | 否 |
| graveyard（墓地） | `graveyard/` | 物理保留 | 不参与检索 |

## 三副本

- 本地 git 仓（工作副本）
- 裸仓（同机或内网中转，`git init --bare`）
- GitHub 私有库（异地）

同步脚本逐份推送，GitHub 失败显式报错——这是最容易静默丢的一份。
Windows 侧用任务计划程序执行同一个脚本。

## 情绪与关系

`emotion.json` 保存 `mood{label,intensity0,since,tau}` 与
`relationship{affinity,trust,events}`。读取时按当前时间现算强度，不写回；
只有事件才修改状态。这样"冷却"是连续函数，不是定时器。
