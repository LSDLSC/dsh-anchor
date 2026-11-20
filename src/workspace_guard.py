#!/usr/bin/env python3
"""DSH 会话注册表守护。

背景：DSH 的会话列表只认 ``<DSH_HOME>/storages/workspace.json`` 里的
``tables.workspaces[].sessionIds``，不扫描 ``sessions/`` 目录。任何一次
"注册表被旧进程用内存快照整体写回"，会话就会在 UI 里凭空消失——文件还在磁盘上，
只是没人登记。这个脚本做两件事：

1. 把 ``updatedAt`` 的毫秒数字修成 ISO 字符串（旧版进程/工具留下的坏数据，
   新版 schema 只接受字符串，一行坏数据会让整个 workspace 域加载失败）；
2. 对比磁盘上的会话目录和已注册的 sessionIds，把漏登记的补进去。

只在检测到问题时才写盘；本身纯本地、零依赖（标准库）。

环境变量：
  DSH_HOME    DSH 数据根目录，默认 ``~/.dsh``
  RESTART_CMD 可选，写回后要执行的生效命令（例如 ``systemctl restart dsh-web``）

用法：
  DSH_HOME=/home/user/.dsh python3 workspace_guard.py
"""
from __future__ import annotations

import glob
import json
import os
import shutil
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

DSH_HOME = Path(os.environ.get("DSH_HOME") or Path.home() / ".dsh")
WS = DSH_HOME / "storages" / "workspace.json"
LOG = Path(os.environ.get("GUARD_LOG") or "/var/log/dsh-workspace-guard.log")


def log(msg: str) -> None:
    line = f"{time.strftime('%Y-%m-%d %H:%M:%S')} {msg}"
    print(line)
    try:
        LOG.parent.mkdir(parents=True, exist_ok=True)
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass


def norm(sid: str) -> str:
    return sid[8:] if sid.startswith("session-") else sid


def session_dir_of(workspace_path: str | None) -> Path | None:
    """把工作区路径编码成 sessions 目录名（DSH 的 ``--path--`` 规则）。"""
    if not workspace_path:
        return None
    try:
        p = Path(workspace_path).resolve()
    except OSError:
        return None
    slug = "-" + str(p).replace("/", "-").replace(":", "").strip("-") + "-"
    return DSH_HOME / "sessions" / slug


def main() -> int:
    if not WS.exists():
        log(f"{WS} 不存在，跳过")
        return 0
    try:
        data = json.loads(WS.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        log(f"读取失败：{e}")
        return 1

    workspaces = data.get("tables", {}).get("workspaces")
    if not workspaces:
        log("没有 workspaces 表，跳过")
        return 0
    ws = next(iter(workspaces.values())) if isinstance(workspaces, dict) else workspaces[0]

    changed = False

    ua = ws.get("updatedAt")
    if isinstance(ua, (int, float)) and not isinstance(ua, bool):
        iso = (
            datetime.fromtimestamp(ua / 1000, tz=timezone.utc)
            .isoformat(timespec="milliseconds")
            .replace("+00:00", "Z")
        )
        ws["updatedAt"] = iso
        changed = True
        log(f"updatedAt 数字已修正：{ua} -> {iso}")

    sess_dir = session_dir_of(ws.get("path"))
    if sess_dir is None or not sess_dir.exists():
        log(f"会话目录不存在：{sess_dir}，跳过补注册")
        return 1 if changed else 0

    ids = list(ws.get("sessionIds") or [])
    have = {norm(x) for x in ids}
    disk = sorted(os.path.basename(p) for p in glob.glob(str(sess_dir / "*")) if os.path.isdir(p))
    missing = [d for d in disk if norm(d) not in have]
    if missing:
        changed = True
        ws["sessionIds"] = ids + missing
        log(f"补注册 {len(missing)} 个会话：{missing}")

    if not changed:
        return 0

    backup = f"{WS}.bak-guard-{time.strftime('%Y%m%d-%H%M%S')}"
    shutil.copy2(WS, backup)
    tmp = f"{WS}.tmp-guard"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
    os.replace(tmp, WS)
    log(f"已写回（备份 {backup}）")

    restart = os.environ.get("RESTART_CMD")
    if missing and restart:
        r = subprocess.run(restart, shell=True, capture_output=True, text=True)
        log(f"重启命令 {'成功' if r.returncode == 0 else '失败'}：{restart}")
        if r.returncode != 0:
            log(r.stderr.strip())
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
