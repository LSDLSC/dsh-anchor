#!/usr/bin/env bash
# 一行安装（发布后可用）：
#   curl -fsSL https://raw.githubusercontent.com/<owner>/anchor/main/quickstart/bootstrap.sh | bash
#
# 不下载仓库，直接取需要的脚本；已经装过就跳过（幂等）。
set -euo pipefail

REPO="${ANCHOR_REPO:-https://raw.githubusercontent.com/OWNER/anchor/main}"
MEM_DIR="${MEM_DIR:-$HOME/.anchor/memory}"
BIN="${BIN:-$HOME/.local/bin}"

say() { printf '%s\n' "$*"; }

say "== Anchor 安装"
mkdir -p "$MEM_DIR"/{journal,graveyard,soul} "$BIN"
[ -f "$MEM_DIR/facts.jsonl" ] || : > "$MEM_DIR/facts.jsonl"
say "记忆目录：$MEM_DIR"

for f in memory.py activation.py anchor.py; do
  target="$BIN/${f%.py}"
  if [ -x "$target" ]; then
    say "跳过（已存在）：$target"
    continue
  fi
  say "下载 $f"
  if command -v curl >/dev/null 2>&1; then
    curl -fsSL "$REPO/src/$f" -o "$target"
  elif command -v wget >/dev/null 2>&1; then
    wget -qO "$target" "$REPO/src/$f"
  else
    say "需要 curl 或 wget" >&2; exit 1
  fi
  chmod +x "$target"
done

say
say "完成。试一下："
say "  export MEMORY_DIR=$MEM_DIR"
say "  memory add \"第一条记忆\" --tags 示例"
say "  memory search 记忆"
say "  anchor check"
