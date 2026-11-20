# 开发源文件

| 文件 | 作用 | 依赖 |
|---|---|---|
| `memory.py` | 四层记忆 CRUD + 检索 + 墓地（bury/restore） | 标准库 |
| `activation.py` | ACT-R 激活打分 + tick（记访问） | 标准库 |
| `emotion.py` | 情绪状态机（指数衰减 + 事件三档）+ 关系刻度 | 标准库 |
| `emotion_auto.py` | 从一段对话自动轻推情绪 | 标准库 |
| `memory_view.py` | 生成单文件 HTML 总览（事实/经历/墓地） | 标准库 |
| `workspace_guard.py` / `registry_guard.py` | 会话注册表修复/补登记（dsh / jsonfile 适配器） | 标准库 |
| `anchor.py` | 任务状态汇总（status/check/guard） | 标准库 |
| `memory_digest.mjs` | 会话 → journal 摘要（脱敏） | Node 18+ |

## 目录结构（记忆库）

```
memory/
├── hot.md            # 常驻判断规则
├── facts.jsonl       # 事实条目（id/ts/text/tags/importance/access_times）
├── journal/          # 每日会话摘要
├── graveyard/        # 墓地（退出检索，可 restore）
├── soul/             # 人格锚点（不进遗忘）
├── emotion.json      # 情绪状态 + 关系刻度（按小时衰减）
└── state.json        # 交接状态
```

## 约定

- `facts.jsonl` 每行一个 JSON 对象，`id = sha256(text)[:8]`
- `access_times` 只保留最近 20 次（防止无限膨胀）
- 所有写操作先备份 `.bak-<ts>`
- 检索命中自动 `tick`（检索即复习）
- `emotion.json` 只存"基准强度 + 起点 + tau"，现算强度不落盘；写入前同样留 `.bak`
