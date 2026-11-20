#!/usr/bin/env bash
# Anchor Quickstart —— 给 DSH 装一套最小可用的记忆可靠性工具
#
# 做三件事：
#   1. 建记忆目录骨架（hot / facts / journal / graveyard / soul）
#   2. 把工具脚本装到 ~/.local/bin
#   3. 可选：装 systemd 定时任务（守卫每小时、沉淀每天 23:50）
#
# 用法：
#   ./install.sh                 # 只装脚本和目录
#   ./install.sh --with-timers   # 同时装 systemd timer（需要 root）
#   ./install.sh --dir ~/mymem   # 自定义记忆目录
set -euo pipefail

DSH_HOME="${DSH_HOME:-$HOME/.dsh}"
MEM_DIR="${MEM_DIR:-$DSH_HOME/memory}"
BIN="${BIN:-$HOME/.local/bin}"
SRC="$(cd "$(dirname "$0")/.." && pwd)/src"
WITH_TIMERS=0

while [ $# -gt 0 ]; do
  case "$1" in
    --with-timers) WITH_TIMERS=1; shift ;;
    --dir) MEM_DIR="$2"; shift 2 ;;
    *) echo "unknown arg: $1"; exit 2 ;;
  esac
done

echo "[1/3] 记忆目录：$MEM_DIR"
mkdir -p "$MEM_DIR"/{journal,graveyard,soul}
[ -f "$MEM_DIR/facts.jsonl" ] || : > "$MEM_DIR/facts.jsonl"
[ -f "$MEM_DIR/hot.md" ] || cat > "$MEM_DIR/hot.md" <<'EOF'
# 常驻人格层（hot）

> 每轮先读，只放判断规则；不放事实细节。

- 先认人，再干活。
- 不确定就说不确定，不编。
EOF
[ -f "$MEM_DIR/soul/README.md" ] || cat > "$MEM_DIR/soul/README.md" <<'EOF'
# Soul（不遗忘层）

这里的文件不参与衰减、压缩、清理、墓地机制。

- `soul.md`：人格锚点（我是谁 / 我和谁 / 性格 / 底线）
- 自动任务只读不写；改动需要主人点头，改完在 CHANGELOG.md 记一行
EOF

echo "[2/3] 安装脚本到 $BIN"
mkdir -p "$BIN"
for f in memory.py activation.py emotion.py workspace_guard.py; do
  cp "$SRC/$f" "$BIN/${f%.py}"
done
cp "$SRC/memory_digest.mjs" "$BIN/memory_digest.mjs"
chmod +x "$BIN"/memory "$BIN"/activation "$BIN"/emotion "$BIN"/workspace_guard "$BIN"/memory_digest.mjs 2>/dev/null || true

echo "[3/3] 验证"
"$BIN/memory" stats 2>/dev/null || printf '%s\n' "memory 脚本已安装，运行 'memory add --text \"...\" --tags demo' 试写一条"
echo
echo "完成。常用命令："
echo "  memory search <关键字>        # 检索（命中会自动记一次访问）"
echo "  activation score              # 看当前激活排序"
echo "  emotion show --inject         # 看情绪状态一行"
echo "  workspace_guard.py            # 修会话注册表（DSH_HOME 指向你的 .dsh）"
echo "  node memory_digest.mjs 24     # 把最近 24h 会话抽成 journal"

if [ "$WITH_TIMERS" = "1" ]; then
  echo
  echo "[systemd] 需要 root：把 deploy/systemd/*.service 里的 DSH_HOME 改成 $DSH_HOME 后执行"
  echo "  cp deploy/systemd/dsh-memory-guard.{service,timer} /etc/systemd/system/"
  echo "  systemctl daemon-reload && systemctl enable --now dsh-memory-guard.timer"
fi
