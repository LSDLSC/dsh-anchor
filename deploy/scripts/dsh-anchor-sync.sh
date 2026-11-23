#!/usr/bin/env bash
# dsh-anchor-sync.sh —— 检查 dsh-anchor 仓库与线上记忆脚本是否一致。
#
# 只检测，不覆盖线上代码。结果写 $DSH_HOME/state/anchor/anchor-sync.json，
# `anchor status` 会把它当成一个任务显示，并记录"连续一致"的起点。
#
# 环境变量：
#   MEMORY_DIR     记忆目录（默认 $DSH_HOME/memory）
#   ANCHOR_REPO    仓库路径（默认 $HOME/workspace/anchor）
#   DSH_HOME       DSH 根目录（默认 $HOME/.dsh）
#   ANCHOR_GIT_TIMEOUT  git pull 超时秒数（默认 30）
set -u

export PATH=/usr/local/bin:/usr/bin:/bin

DSH_HOME="${DSH_HOME:-$HOME/.dsh}"
MEMORY_DIR="${MEMORY_DIR:-$DSH_HOME/memory}"
MEMORY_DIR="${MEMORY_DIR%/}"
REPO_DIR="${ANCHOR_REPO:-$HOME/workspace/anchor}"
STATE_DIR="$DSH_HOME/state/anchor"
GIT_TIMEOUT="${ANCHOR_GIT_TIMEOUT:-30}"

# 参与比对的脚本；新增脚本时改这一行
FILES=(memory.py emotion.py emotion_auto.py activation.py memory_view.py)

STAMP="$(date '+%Y-%m-%d %H:%M:%S')"
TS="$(date +%s)"
err=""
repo_rev="-"

if [ -d "$REPO_DIR/.git" ]; then
  pull_out="$(timeout "$GIT_TIMEOUT" git -C "$REPO_DIR" pull --ff-only -q 2>&1)" \
    || err="git pull 失败：$(printf '%s\n' "$pull_out" | tail -n 1)"
  repo_rev="$(git -C "$REPO_DIR" rev-parse --short HEAD 2>/dev/null || echo '-')"
else
  err="仓库不存在：$REPO_DIR"
fi

fail=0
lines=""
for f in "${FILES[@]}"; do
  src="$REPO_DIR/src/$f"
  live="$MEMORY_DIR/scripts/$f"
  if [ ! -f "$src" ]; then
    lines+="$f:missing_src"$'\n'; fail=1
  elif [ ! -f "$live" ]; then
    lines+="$f:missing_live"$'\n'; fail=1
  else
    a="$(sha256sum "$src" | cut -d' ' -f1)"
    b="$(sha256sum "$live" | cut -d' ' -f1)"
    if [ "$a" = "$b" ]; then
      lines+="$f:ok"$'\n'
    else
      lines+="$f:drift"$'\n'; fail=1
    fi
  fi
done

detail=""
if [ "$fail" -ne 0 ]; then
  detail="$(printf '%s' "$lines" | grep -v ':ok$' | paste -sd ' ' -)"
fi

mkdir -p "$STATE_DIR"
export SYNC_TS="$TS" SYNC_AT="$STAMP" SYNC_OK="$([ "$fail" -eq 0 ] && echo 1 || echo 0)" \
       SYNC_REPO_REV="$repo_rev" SYNC_FILES="$lines" SYNC_DETAIL="$detail" SYNC_ERR="$err" \
       SYNC_REPO="$REPO_DIR" SYNC_MEM="$MEMORY_DIR"

python3 - "$STATE_DIR/anchor-sync.json" <<'PY'
import json, os, sys, time
from datetime import datetime

path = sys.argv[1]
prev = {}
try:
    with open(path, encoding="utf-8") as fh:
        prev = json.load(fh)
except (OSError, json.JSONDecodeError):
    prev = {}

ok = os.environ.get("SYNC_OK") == "1"
now = time.time()
since = prev.get("consistent_since") if ok else None
if ok and not since:
    since = now

files = {}
for line in (os.environ.get("SYNC_FILES") or "").splitlines():
    name, _, state = line.partition(":")
    if name:
        files[name] = state

detail = os.environ.get("SYNC_DETAIL") or ""
if not detail:
    days = (now - float(since)) / 86400.0 if since else 0.0
    detail = f"全部一致（连续 {days:.1f} 天）"
err = os.environ.get("SYNC_ERR") or ""
if err:
    detail = f"{detail}；{err}"

rec = {
    "task": "anchor-sync",
    "ts": now,
    "at": os.environ.get("SYNC_AT") or datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    "ok": ok,
    "changed": False,
    "detail": detail,
    "error": err,
    "repo": os.environ.get("SYNC_REPO") or "",
    "memory_dir": os.environ.get("SYNC_MEM") or "",
    "repo_rev": os.environ.get("SYNC_REPO_REV") or "-",
    "files": files,
    "consistent_since": since,
}

tmp = path + ".tmp"
with open(tmp, "w", encoding="utf-8") as fh:
    json.dump(rec, fh, ensure_ascii=False, indent=1)
os.replace(tmp, path)
print(detail)
PY
