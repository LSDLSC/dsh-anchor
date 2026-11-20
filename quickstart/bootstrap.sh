#!/usr/bin/env bash
# 一行安装（发布后可用）：
#   curl -fsSL https://raw.githubusercontent.com/<owner>/anchor/main/quickstart/bootstrap.sh | bash
#
# 不下载整个仓库，只取要装的脚本；已经装过就跳过（幂等）。
# 与 install.sh 的区别：install.sh 面向已 clone 的仓库/分发包，bootstrap 面向裸机。
set -euo pipefail

REPO="${ANCHOR_REPO:-https://raw.githubusercontent.com/OWNER/anchor/main}"
MEM_DIR="${MEMORY_DIR:-$HOME/.dsh/memory}"
BIN="${BIN:-$HOME/.local/bin}"

say() { printf '%s\n' "$*"; }

say "== Anchor 安装"
mkdir -p "$MEM_DIR"/{journal,graveyard,soul} "$BIN" "$BIN/adapters"
[ -f "$MEM_DIR/facts.jsonl" ] || : > "$MEM_DIR/facts.jsonl"
say "记忆目录：$MEM_DIR"

fetch() {
  local url="$1" out="$2"
  if [ -f "$out" ]; then
    say "跳过（已存在）：$out"
    return 0
  fi
  say "下载 $(basename "$out")"
  if command -v curl >/dev/null 2>&1; then
    curl -fsSL "$url" -o "$out"
  elif command -v wget >/dev/null 2>&1; then
    wget -qO "$out" "$url"
  else
    say "需要 curl 或 wget" >&2; exit 1
  fi
}

for f in memory.py activation.py workspace_guard.py anchor.py registry_guard.py; do
  fetch "$REPO/src/$f" "$BIN/$f"
done
for a in base.py dsh.py jsonfile.py __init__.py; do
  fetch "$REPO/src/adapters/$a" "$BIN/adapters/$a"
done
fetch "$REPO/src/memory_digest.mjs" "$BIN/memory_digest.mjs"

# wrapper：钉住 MEMORY_DIR，避免脚本按自身目录推算
cat > "$BIN/memory" <<EOF
#!/usr/bin/env bash
export MEMORY_DIR="\${MEMORY_DIR:-$MEM_DIR}"
exec python3 "$BIN/memory.py" "\$@"
EOF
cat > "$BIN/activation" <<EOF
#!/usr/bin/env bash
export MEMORY_DIR="\${MEMORY_DIR:-$MEM_DIR}"
exec python3 "$BIN/activation.py" "\$@"
EOF
chmod +x "$BIN"/memory "$BIN"/activation "$BIN"/*.py "$BIN/adapters"/*.py "$BIN/memory_digest.mjs" 2>/dev/null || true

say
say "完成。试一下："
say "  memory add \"第一条记忆\" --tags 示例"
say "  memory search 记忆"
say "  anchor.py check"
