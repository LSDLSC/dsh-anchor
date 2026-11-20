#!/usr/bin/env python3
"""Anchor 控制台 —— 看状态、跑自检、执行维护动作。

设计目标：把"守卫/同步/沉淀跑没跑、跑成了没有"变成一条命令能回答的事。
所有任务执行后写一份结构化结果到 ``$DSH_HOME/state/anchor/<task>.json``，
`status` 只读这些结果，不解析日志。

用法：
  anchor status                 # 所有任务最近状态（含超期判断）
  anchor status --json          # 机器可读
  anchor guard                  # 手动跑一次注册表守卫
  anchor check                  # 自检：环境、路径、依赖、权限
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

DSH_HOME = Path(os.environ.get("DSH_HOME") or Path.home() / ".dsh")
STATE_DIR = DSH_HOME / "state" / "anchor"
MEMORY_DIR = Path(os.environ.get("MEMORY_DIR") or DSH_HOME / "memory")

# task -> (中文名, 预期间隔秒, 说明)
TASKS = {
    "guard": ("注册表守卫", 3600, "每小时修 updatedAt / 补登记会话"),
    "digest": ("会话沉淀", 86400, "每天 23:50 把会话抽成 journal"),
    "sync": ("三副本同步", 600, "每 10 分钟推 本地→裸仓→GitHub"),
}


def now_ts() -> float:
    return time.time()


def fmt_ts(ts: float | None) -> str:
    if not ts:
        return "从未"
    return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M")


def read_result(task: str) -> dict | None:
    p = STATE_DIR / f"{task}.json"
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def write_result(task: str, ok: bool, changed: bool = False, detail: str = "", error: str = "") -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    rec = {
        "task": task,
        "ts": now_ts(),
        "at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "ok": ok,
        "changed": changed,
        "detail": detail,
        "error": error,
    }
    tmp = STATE_DIR / f".{task}.json.tmp"
    tmp.write_text(json.dumps(rec, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, STATE_DIR / f"{task}.json")


def cmd_status(args: argparse.Namespace) -> int:
    rows = []
    for task, (name, interval, desc) in TASKS.items():
        r = read_result(task)
        if not r:
            rows.append({"task": task, "name": name, "state": "从未运行", "last": "从未",
                         "age": None, "interval": interval, "ok": None, "detail": desc})
            continue
        age = now_ts() - float(r.get("ts") or 0)
        if not r.get("ok"):
            state = "失败"
        elif age > interval * 2:
            state = "超期"
        else:
            state = "正常"
        rows.append({"task": task, "name": name, "state": state, "last": r.get("at"),
                     "age": age, "interval": interval, "ok": r.get("ok"),
                     "changed": r.get("changed"), "detail": r.get("detail") or "",
                     "error": r.get("error") or ""})

    if args.json:
        print(json.dumps({"generated_at": fmt_ts(now_ts()), "rows": rows}, ensure_ascii=False, indent=2))
        return 0 if all(r["state"] == "正常" for r in rows) else 1

    print(f"Anchor 状态  {fmt_ts(now_ts())}")
    print(f"  DSH_HOME   {DSH_HOME}")
    print(f"  记忆目录   {MEMORY_DIR}")
    print()
    bad = 0
    for r in rows:
        if r["state"] != "正常":
            bad += 1
        age = f"{r['age'] / 60:.0f} 分钟前" if r["age"] is not None else "—"
        mark = {"正常": "OK ", "失败": "ERR", "超期": "LATE", "从未运行": "NEW "}[r["state"]]
        print(f"  [{mark}] {r['name']:<8} {r['state']:<6} 最后 {r['last']}（{age}）")
        if r.get("error"):
            print(f"        错误：{r['error']}")
        elif r.get("changed"):
            print(f"        本次有变更：{r['detail']}")
    print()
    if bad:
        print(f"{bad} 项需要关注")
        return 1
    print("全部正常")
    return 0


def cmd_guard(args: argparse.Namespace) -> int:
    script = Path(os.environ.get("ANCHOR_GUARD") or Path(__file__).with_name("workspace_guard.py"))
    if not script.exists():
        print(f"找不到守卫脚本：{script}", file=sys.stderr)
        return 2
    import subprocess
    r = subprocess.run([sys.executable, str(script)], capture_output=True, text=True,
                       env=os.environ.copy())
    out = (r.stdout or "").strip().splitlines()
    detail = "；".join(out[-2:]) if out else ""
    write_result("guard", r.returncode == 0, changed="已写回" in "".join(out), detail=detail,
                 error=(r.stderr or "").strip()[:300])
    print(r.stdout.strip() or "(无输出)")
    if r.returncode != 0:
        print(r.stderr.strip(), file=sys.stderr)
        return r.returncode
    return 0


def cmd_check(args: argparse.Namespace) -> int:
    problems = 0

    def line(ok: bool, label: str, note: str = "") -> None:
        nonlocal problems
        if not ok:
            problems += 1
        print(f"  {'OK ' if ok else 'ERR'} {label}" + (f"  {note}" if note else ""))

    print("环境")
    line(sys.version_info >= (3, 10), f"Python {sys.version.split()[0]}（需要 3.10+）")
    for tool in ("git", "node"):
        line(shutil.which(tool) is not None, f"{tool} 可用")

    print("路径")
    line(DSH_HOME.exists(), f"DSH_HOME 存在  {DSH_HOME}")
    line((DSH_HOME / "storages" / "workspace.json").exists(), "workspace.json 存在")
    line(MEMORY_DIR.exists(), f"记忆目录存在  {MEMORY_DIR}")
    for sub in ("journal", "graveyard"):
        line((MEMORY_DIR / sub).exists(), f"  {sub}/ 存在")

    print("数据")
    facts = MEMORY_DIR / "facts.jsonl"
    if facts.exists():
        n = sum(1 for ln in facts.read_text(encoding="utf-8").splitlines() if ln.strip())
        line(True, f"facts.jsonl  {n} 条")
    else:
        line(False, "facts.jsonl 不存在")

    print("任务状态")
    for task in TASKS:
        r = read_result(task)
        line(r is not None, f"{TASKS[task][0]}（{task}）有运行记录" if r else f"{TASKS[task][0]}（{task}）从未运行")

    print()
    if problems:
        print(f"{problems} 项异常")
        return 1
    print("自检通过")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(prog="anchor", description="Anchor 记忆可靠性控制台")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("status", help="所有任务最近状态")
    s.add_argument("--json", action="store_true")
    s.set_defaults(func=cmd_status)

    g = sub.add_parser("guard", help="手动跑注册表守卫")
    g.set_defaults(func=cmd_guard)

    c = sub.add_parser("check", help="自检环境/路径/依赖")
    c.set_defaults(func=cmd_check)

    args = p.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
