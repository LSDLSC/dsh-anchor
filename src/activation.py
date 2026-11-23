#!/usr/bin/env python3
"""ACT-R 激活 + 概率召回原型。

机制（engram-ai / mtrace 同款，纯本地、零依赖）：
  基础激活  B = ln( Σ_j (t_j + 1)^(-0.5) )   # t_j = 第 j 次访问距今小时数
  总激活    A = B + ε                         # ε ~ N(0, 0.5)，噪声 = "突然想起来"
  召回概率  P = σ(A - τ)                      # 逻辑斯蒂，τ 可调

用法：
  activation.py score [--top 15] [--tau -1.5] [--no-noise]
  activation.py tick <id>                      # 记一次访问（追加 access_times）
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import random
import sys
from datetime import datetime
from pathlib import Path

def memory_root() -> Path:
    """记忆目录：MEMORY_DIR → WHALE_MEMORY_DIR → 脚本上一级（像记忆库时）→ $DSH_HOME/memory。"""
    env = os.environ
    if env.get("MEMORY_DIR"):
        return Path(env["MEMORY_DIR"]).expanduser()
    if env.get("WHALE_MEMORY_DIR"):
        return Path(env["WHALE_MEMORY_DIR"]).expanduser()
    local = Path(__file__).resolve().parent.parent
    if (local / "facts.jsonl").exists() or (local / "hot.md").exists():
        return local
    return Path(env.get("DSH_HOME") or Path.home() / ".dsh") / "memory"


ROOT = memory_root()
FACTS = ROOT / "facts.jsonl"


def load_facts() -> list[dict]:
    if not FACTS.exists():
        return []
    out = []
    for line in FACTS.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict) and obj.get("text"):
            out.append(obj)
    return out


def fact_id(f: dict) -> str:
    return hashlib.sha256(f.get("text", "").encode("utf-8")).hexdigest()[:8]


def parse_ts(s: str) -> datetime | None:
    s = (s or "").strip()
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(s[: len(fmt) + 2] if "%f" in fmt else s[:16], fmt)
        except ValueError:
            continue
    return None


def access_times(f: dict) -> list[datetime]:
    raw = f.get("access_times") or [f.get("ts", "")]
    out = [t for t in (parse_ts(x) for x in raw) if t]
    return out or [datetime.now()]


def base_activation(f: dict, now: datetime) -> float:
    hours = []
    for t in access_times(f):
        h = max((now - t).total_seconds() / 3600.0, 0.0)
        hours.append(h)
    if not hours:
        return -5.0
    s = sum((h + 1.0) ** -0.5 for h in hours)
    return math.log(s) if s > 0 else -10.0


def importance_of(f: dict) -> float:
    """条目的重要性，缺省按 tags 推：身份/规矩/纪律/安全=5，偏好/环境=4，其他=3。"""
    raw = f.get("importance")
    if isinstance(raw, (int, float)) and raw > 0:
        return float(raw)
    tags = set(f.get("tags") or [])
    if tags & {"身份", "称呼", "规矩", "纪律", "安全", "soul"}:
        return 5.0
    if tags & {"偏好", "环境", "工作区"}:
        return 4.0
    return 3.0


IMPORTANCE_WEIGHT = 0.4


def total_activation(f: dict, now: datetime, noise: bool) -> float:
    a = base_activation(f, now)
    a += IMPORTANCE_WEIGHT * importance_of(f)
    if noise:
        a += random.gauss(0.0, 0.5)
    return a


def prob(a: float, tau: float) -> float:
    return 1.0 / (1.0 + math.exp(-(a - tau)))


def cmd_score(args: argparse.Namespace) -> None:
    facts = load_facts()
    if not facts:
        print("库是空的")
        return
    now = datetime.now()
    rows = []
    for f in facts:
        a = total_activation(f, now, not args.no_noise)
        rows.append((prob(a, args.tau), a, f))
    rows.sort(key=lambda x: -x[0])
    print(f"共 {len(facts)} 条，τ={args.tau}，噪声={'开' if not args.no_noise else '关'}；按召回概率排序：")
    for p, a, f in rows[: args.top]:
        tags = ",".join(f.get("tags", []))
        ts = f.get("ts", "")[:16]
        print(f"  P={p:.3f}  A={a:+.2f}  I={importance_of(f):.0f}  [{fact_id(f)}] {ts} {f['text'][:46]}" + (f"  #{tags}" if tags else ""))
    if len(rows) > args.top:
        print(f"  … 其余 {len(rows) - args.top} 条概率更低")


def cmd_tick(args: argparse.Namespace) -> None:
    facts = load_facts()
    target = [f for f in facts if fact_id(f) == args.id]
    if not target:
        print(f"没有 id={args.id} 的事实", file=sys.stderr)
        return
    now = datetime.now()
    stamp = now.strftime("%Y-%m-%d %H:%M")
    for f in facts:
        if fact_id(f) == args.id:
            times = list(f.get("access_times") or [])
            if not times:
                times = [f.get("ts", stamp)]
            times.append(stamp)
            f["access_times"] = times[-20:]
    backup = FACTS.with_name(FACTS.name + ".bak-" + now.strftime("%Y%m%d-%H%M%S"))
    if FACTS.exists():
        backup.write_bytes(FACTS.read_bytes())
    tmp = FACTS.with_suffix(FACTS.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as fh:
        for f in facts:
            fh.write(json.dumps(f, ensure_ascii=False) + "\n")
    tmp.replace(FACTS)
    print(f"已记一次访问 [{args.id}]，备份 {backup.name}")


def main() -> None:
    p = argparse.ArgumentParser(description="ACT-R 激活打分（只读）与访问记录")
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("score", help="按激活/召回概率排序")
    s.add_argument("--top", type=int, default=15)
    s.add_argument("--tau", type=float, default=-1.5)
    s.add_argument("--no-noise", action="store_true")
    s.set_defaults(func=cmd_score)
    t = sub.add_parser("tick", help="给一条事实记一次访问")
    t.add_argument("id")
    t.set_defaults(func=cmd_tick)
    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
