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

import contextlib
import glob
import json
import os
import shutil
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

try:
    import fcntl  # Linux / macOS
except ImportError:  # Windows
    fcntl = None

DSH_HOME = Path(os.environ.get("DSH_HOME") or Path.home() / ".dsh")
WS = DSH_HOME / "storages" / "workspace.json"
LOG = Path(os.environ.get("GUARD_LOG") or "/var/log/dsh-workspace-guard.log")


@contextlib.contextmanager
def file_lock(path: Path):
    """对注册表加排他锁，保证"读-改-写"期间没有别的守卫进程插进来。

    Windows 没有 fcntl：退化为无锁，并打一条提示。真正的防覆盖靠
    "写前重读合并"（见 main），锁只是把窗口缩到最小。
    """
    if fcntl is None:
        log("当前平台无 fcntl，跳过文件锁（仍会做写前合并）")
        yield
        return
    lock_path = path.with_suffix(path.suffix + ".lock")
    fh = open(lock_path, "w")
    try:
        fcntl.flock(fh, fcntl.LOCK_EX)
        yield
    finally:
        fcntl.flock(fh, fcntl.LOCK_UN)
        fh.close()


def write_result(ok: bool, changed: bool, detail: str = "", error: str = "") -> None:
    """写结构化结果，供 `anchor status` 汇总（不写的话 status 会显示"从未运行"）。"""
    state_dir = DSH_HOME / "state" / "anchor"
    try:
        state_dir.mkdir(parents=True, exist_ok=True)
        rec = {"task": "guard", "ts": time.time(),
               "at": time.strftime("%Y-%m-%d %H:%M:%S"),
               "ok": ok, "changed": changed, "detail": detail, "error": error}
        tmp = state_dir / ".guard.json.tmp"
        tmp.write_text(json.dumps(rec, ensure_ascii=False, indent=1), encoding="utf-8")
        os.replace(tmp, state_dir / "guard.json")
    except OSError:
        pass


def log(msg: str) -> None:
    line = f"{time.strftime('%Y-%m-%d %H:%M:%S')} {msg}"
    print(line)
    try:
        LOG.parent.mkdir(parents=True, exist_ok=True)
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass


def iso_of(ms: float) -> str:
    return (
        datetime.fromtimestamp(ms / 1000, tz=timezone.utc)
        .isoformat(timespec="milliseconds")
        .replace("+00:00", "Z")
    )


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
    # DSH 的目录命名规则：-- + 路径（去前导分隔符、分隔符换 -、去掉冒号）+ --
    slug = "--" + str(p).lstrip("/\\").replace("\\", "-").replace("/", "-").replace(":", "") + "--"
    return DSH_HOME / "sessions" / slug


def main() -> int:
    if not WS.exists():
        log(f"{WS} 不存在，跳过")
        write_result(True, False, "workspace.json 不存在，跳过")
        return 0
    with file_lock(WS):
        return _main_locked()


def _merge_into(latest: dict, disk_ids: list[str]) -> tuple[bool, list[str]]:
    """把磁盘上未登记的会话并进最新注册表，返回 (是否改动, 新增列表)。"""
    workspaces = latest.get("tables", {}).get("workspaces")
    if not workspaces:
        return False, []
    ws = next(iter(workspaces.values())) if isinstance(workspaces, dict) else workspaces[0]
    ids = list(ws.get("sessionIds") or [])
    have = {norm(x) for x in ids}
    missing = [d for d in disk_ids if norm(d) not in have]
    if missing:
        ws["sessionIds"] = ids + missing
        return True, missing
    return False, []


def _main_locked() -> int:
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
        iso = iso_of(ua)
        ws["updatedAt"] = iso
        changed = True
        log(f"updatedAt 数字已修正：{ua} -> {iso}")

    sess_dir = session_dir_of(ws.get("path"))
    if sess_dir is None or not sess_dir.exists():
        log(f"会话目录不存在：{sess_dir}，跳过补注册")
        write_result(True, changed, f"会话目录不存在：{sess_dir}")
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
        write_result(True, False, "无变更")
        return 0

    # 写前重读：检查期间宿主可能已经写入新清单，直接覆盖会把它冲掉。
    try:
        latest = json.loads(WS.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        latest = data
    # 新读到的内容如果还是数字 updatedAt，也要一起修
    latest_ws = next(iter(latest.get("tables", {}).get("workspaces", {}).values()), None)
    if isinstance(latest_ws, dict) and isinstance(latest_ws.get("updatedAt"), (int, float)):
        latest_ws["updatedAt"] = iso_of(latest_ws["updatedAt"])
        log("写前重读的 updatedAt 也是数字，已一并修正")
    merged, missing2 = _merge_into(latest, disk)
    if missing2:
        log(f"写前重读又发现 {len(missing2)} 个未登记：{missing2}")

    backup = f"{WS}.bak-guard-{time.strftime('%Y%m%d-%H%M%S')}"
    shutil.copy2(WS, backup)
    tmp = f"{WS}.tmp-guard"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(latest if merged else data, f, ensure_ascii=False, separators=(",", ":"))
    os.replace(tmp, WS)
    log(f"已写回（备份 {backup}）")

    write_result(True, True, f"补登记 {len(missing2 or missing)} 个会话")
    restart = os.environ.get("RESTART_CMD")
    if (missing or missing2) and restart:
        r = subprocess.run(restart, shell=True, capture_output=True, text=True)
        log(f"重启命令 {'成功' if r.returncode == 0 else '失败'}：{restart}")
        if r.returncode != 0:
            log(r.stderr.strip())
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
