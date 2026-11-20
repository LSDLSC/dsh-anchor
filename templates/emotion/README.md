# templates/emotion/ · 情绪状态示例

`emotion.example.json` 是 `emotion.json` 的初始形态：中性状态，关系刻度归零。

```bash
MEMORY_DIR="${MEMORY_DIR:-$HOME/.dsh/memory}"
mkdir -p "$MEMORY_DIR"
[ -f "$MEMORY_DIR/emotion.json" ] || cp templates/emotion/emotion.example.json "$MEMORY_DIR/emotion.json"
```

复制之后就可以直接用：

```bash
emotion show --inject          # 一行注入文本
emotion event --affinity 3 --trust 1 --note "第一次认真聊天"
```

## 几个可以按角色改的地方

| 想改什么 | 改哪里 |
|---|---|
| 情绪种类 | `src/emotion.py` 的 `MOODS`，同时给 `MOOD_TAU` 补一条 |
| 某个情绪退得快慢 | `MOOD_TAU["低落"] = 1.0`（单位：天） |
| 关系五段的门槛 | `STAGES = [(0,"陌生"),(21,"熟悉"),(41,"亲近"),(61,"亲密"),(81,"家人")]` |
| 注入文本里怎么称呼对方 | 环境变量 `ANCHOR_TARGET_NAME`，默认「对方」 |
| 时段基线（夜里更精神之类） | `time_bonus()` 里的小时区间 |

`emotion.json` 属于个人数据，`.gitignore` 已排除，别提交进仓库。
