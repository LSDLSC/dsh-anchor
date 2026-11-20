# templates/ · 目录骨架与示例

这里放"长得对"的样本，不是可执行代码。`quickstart/install.sh` 会把它们复制到记忆目录里，
已有文件不覆盖。

| 路径 | 作用 | 是否该改 |
|---|---|---|
| `templates/soul/soul.example.md` | 人格锚点示例，说明该写什么、不该写什么 | 复制成 `soul/soul.md` 后改成你自己的 |
| `templates/soul/README.md` | soul 层的规则（不衰减、改动要留痕、要问过本人） | 一般不用改 |
| `templates/soul/CHANGELOG.example.md` | 每次改 `soul.md` 记一行 | 复制成 `soul/CHANGELOG.md` |
| `templates/graveyard/README.md` | 墓地的语义（移入不销毁、可 restore、不进检索） | 一般不用改 |

## 为什么人格层要单独放

`soul.md` 是"这个 AI 是谁、跟谁是什么关系、底线在哪"。它**不参与遗忘**：
不进墓地、不按激活值降权、不随上下文压缩消失。把它和普通事实混在一个文件里，
迟早会被一次"清理"顺手带走。

代价是它不能自动生长，所以规则写死两条：改要有理由（`CHANGELOG.md` 一行），
改要经本人同意。

## 复制示例

```bash
MEMORY_DIR="${MEMORY_DIR:-$HOME/.dsh/memory}"
mkdir -p "$MEMORY_DIR/soul"
cp templates/soul/soul.example.md "$MEMORY_DIR/soul/soul.md"
cp templates/soul/README.md      "$MEMORY_DIR/soul/README.md"
cp templates/soul/CHANGELOG.example.md "$MEMORY_DIR/soul/CHANGELOG.md"
mkdir -p "$MEMORY_DIR/graveyard"
cp templates/graveyard/README.md "$MEMORY_DIR/graveyard/README.md"
```
