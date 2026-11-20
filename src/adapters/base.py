"""适配器公共件：锁、日志、时间戳、id 归一化、结果写入。"""
from __future__ import annotations

import contextlib
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

try:
    import fcntl  # Linux / macOS
except ImportError:  # Windows
    fcntl = None

LOG_PATH = Path(os.environ.get("GUARD_LOG") or "/var/log/anchor-guard.log")
STATE_HOME = Path(os.environ.get("DSH_HOME") or Path.home() / ".dsh")


def log(msg: str) -> None:
    line = f"{time.strftime('%Y-%m-%d %H:%M:%S')} {msg}"
    print(line)
    try:
        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass


@contextlib.contextmanager
def file_lock(path: Path):
    """读-改-写期间加排他锁。Windows 退化无锁（写前合并仍是主防线）。"""
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


def iso_of(ms: float) -> str:
    return (
        datetime.fromtimestamp(ms / 1000, tz=timezone.utc)
        .isoformat(timespec="milliseconds")
        .replace("+00:00", "Z")
    )


def norm(sid: str) -> str:
    """去掉 ``session-`` 前缀再比较，避免 ``session-x`` 与 ``x`` 被当成两个。"""
    return sid[8:] if sid.startswith("session-") else sid


def write_result(task: str, ok: bool, changed: bool, detail: str = "", error: str = "") -> None:
    state_dir = STATE_HOME / "state" / "anchor"
    try:
        state_dir.mkdir(parents=True, exist_ok=True)
        rec = {"task": task, "ts": time.time(),
               "at": time.strftime("%Y-%m-%d %H:%M:%S"),
               "ok": ok, "changed": changed, "detail": detail, "error": error}
        tmp = state_dir / f".{task}.json.tmp"
        tmp.write_text(json.dumps(rec, ensure_ascii=False, indent=1), encoding="utf-8")
        os.replace(tmp, state_dir / f"{task}.json")
    except OSError:
        pass
