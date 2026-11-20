# 开发源文件

| 文件 | 作用 | 依赖 |
|---|---|---|
| `memory.py` | 四层记忆 CRUD + 检索 + 墓地（bury/restore） | 标准库 |
| `activation.py` | ACT-R 激活打分 + tick（记访问） | 标准库 |
| `emotion.py` | 情绪状态机 + 关系刻度 | 标准库 |
| `workspace_guard.py` | DSH 会话注册表修复/补登记 | 标准库 |
| `memory_digest.mjs` | 会话 → journal 摘要（脱敏） | Node 18+ |

## 目录结构（记忆库）

```
memory/
├── hot.md            # 常驻判断规则
├── facts.jsonl       # 事实条目（id/ts/text/tags/importance/access_times）
├── journal/          # 每日会话摘要
├── graveyard/        # 墓地（退出检索，可 restore）
├── soul/             # 人格锚点（不进遗忘）
└── state.json        # 交接状态
```

## 约定

- `facts.jsonl` 每行一个 JSON 对象，`id = sha256(text)[:8]`
- `access_times` 只保留最近 20 次（防止无限膨胀）
- 所有写操作先备份 `.bak-<ts>`
- 检索命中自动 `tick`（检索即复习）
