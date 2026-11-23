#!/usr/bin/env python3
"""四层记忆小工具（轻量版 + 墓地）。

L1 hot.md 常驻人格；L2 facts.jsonl 事实；L3 journal/ 原文；L4 state.json 交接。
墓地 graveyard/：把"不再参与检索"的旧记忆移出去，物理保留、随时 restore。
只做本地检索/追加/交接/埋葬，不调用模型、不联网、不写人格层。

由 MEMORY_DIR 目录驱动（默认 $DSH_HOME/memory，$DSH_HOME 默认 ~/.dsh）；兼容旧变量 WHALE_MEMORY_DIR。
未设置环境变量时，若脚本上一级目录像记忆库（含 facts.jsonl 或 hot.md），就直接用它。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
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
HOT = ROOT / "hot.md"
STATE = ROOT / "state.json"
FACTS = ROOT / "facts.jsonl"
JOURNAL = ROOT / "journal"
GRAVE = ROOT / "graveyard"
INDEX = GRAVE / "index.json"


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return ""


def load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
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


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    tmp.replace(path)


def load_facts() -> list[dict]:
    return load_jsonl(FACTS)


def fact_id(fact: dict) -> str:
    return hashlib.sha256(fact.get("text", "").encode("utf-8")).hexdigest()[:8]


def importance_of(fact: dict) -> int:
    """条目的重要性，缺省按 tags 推：身份/规矩/纪律/安全=5，偏好/环境=4，其他=3。"""
    raw = fact.get("importance")
    if isinstance(raw, (int, float)) and raw > 0:
        return int(raw)
    tags = set(fact.get("tags") or [])
    if tags & {"身份", "称呼", "规矩", "纪律", "安全", "soul"}:
        return 5
    if tags & {"偏好", "环境", "工作区"}:
        return 4
    return 3


def remember_hits(hits: list[dict]) -> None:
    """检索即复习：给命中的事实追加一次 access_times（只留最近 20 次）。"""
    if not hits:
        return
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    all_facts = load_facts()
    wanted = {fact_id(f) for f in hits}
    changed = False
    for f in all_facts:
        if fact_id(f) in wanted:
            times = list(f.get("access_times") or [])
            if not times:
                times = [f.get("ts", stamp)]
            times.append(stamp)
            f["access_times"] = times[-20:]
            changed = True
    if not changed:
        return
    backup = FACTS.with_name(FACTS.name + ".bak-" + datetime.now().strftime("%Y%m%d-%H%M%S"))
    if FACTS.exists():
        backup.write_bytes(FACTS.read_bytes())
    write_jsonl(FACTS, all_facts)


def load_index() -> list[dict]:
    if not INDEX.exists():
        return []
    try:
        data = json.loads(INDEX.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except json.JSONDecodeError:
        return []


def save_index(rows: list[dict]) -> None:
    INDEX.parent.mkdir(parents=True, exist_ok=True)
    INDEX.write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def terms(query: str) -> list[str]:
    q = query.strip().lower()
    if not q:
        return []
    parts = [p for p in re.split(r"[\s,，。;；/]+", q) if p]
    extra = []
    for p in parts:
        if len(p) >= 3:
            extra.extend(p[i : i + 2] for i in range(len(p) - 1))
    return list(dict.fromkeys(parts + extra))


def score(fact: dict, ts: list[str]) -> int:
    text = (fact.get("text", "") + " " + " ".join(fact.get("tags", []))).lower()
    return sum(1 for t in ts if t in text)


def cmd_search(args: argparse.Namespace) -> None:
    ts = terms(args.query)
    rows = []
    for f in load_facts():
        s = score(f, ts)
        if s:
            rows.append((s, f))
    rows.sort(key=lambda x: (-x[0], x[1].get("ts", "")))
    if not rows:
        print("（没有命中；可以先 add 一条事实）")
        return
    for s, f in rows[: args.limit]:
        tags = ",".join(f.get("tags", []))
        print(f"[{fact_id(f)}] [{s}] {f.get('ts','')} {f['text']}" + (f"  #{tags}" if tags else ""))
    remember_hits([f for _, f in rows[: args.limit]])


def importance_for(tags: list[str]) -> int:
    """没有显式指定时，按标签给默认重要性：身份/规矩/纪律/安全=5，偏好/环境=4，其余 3。"""
    keys = set(tags)
    if keys & {"身份", "规矩", "纪律", "安全", "底线", "soul"}:
        return 5
    if keys & {"偏好", "环境", "项目", "工具"}:
        return 4
    return 3


def cmd_add(args: argparse.Namespace) -> None:
    text = args.text.strip()
    if not text:
        print("空事实，拒绝写入", file=sys.stderr)
        return
    if len(text) > 500:
        print("事实太长（>500 字），请拆成多条", file=sys.stderr)
        return
    tags = [t.strip() for t in (args.tags or "").split(",") if t.strip()]
    imp = args.importance if args.importance is not None else importance_for(tags)
    rec = {"ts": datetime.now().strftime("%Y-%m-%d %H:%M"), "text": text, "tags": tags, "importance": imp}
    with FACTS.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    print(f"已写入 [{fact_id(rec)}]：", rec["text"])


def cmd_handoff(args: argparse.Namespace) -> None:
    print("=== L1 hot.md ===")
    print(read_text(HOT).strip() or "（空）")
    print("\n=== L4 state.json ===")
    print(read_text(STATE).strip() or "（空）")
    if args.query:
        print("\n=== L2 相关事实 ===")
        cmd_search(argparse.Namespace(query=args.query, limit=args.limit))


def cmd_stats(args: argparse.Namespace) -> None:
    facts = load_facts()
    grave = load_index()
    print(f"L1 hot.md: {len(read_text(HOT))} 字")
    print(f"L2 facts: {len(facts)} 条")
    print(f"L3 journal: {len(list(JOURNAL.glob('*.md'))) if JOURNAL.exists() else 0} 个文件")
    print(f"L4 state.json: {len(read_text(STATE))} 字")
    print(f"墓地: {len(grave)} 条（不参与检索，可 restore）")


def cmd_bury(args: argparse.Namespace) -> None:
    facts = load_facts()
    if not facts:
        print("库是空的，没有可埋的东西", file=sys.stderr)
        return

    targets: list[dict] = []
    if args.id:
        targets = [f for f in facts if fact_id(f) == args.id]
    elif args.query:
        ts = terms(args.query)
        hits = [f for f in facts if score(f, ts) > 0]
        if not hits:
            print("没有匹配的事实", file=sys.stderr)
            return
        if len(hits) > 1 and not args.all:
            print("命中多条，加 --all 或改用 --id：", file=sys.stderr)
            for f in hits:
                print(f"  [{fact_id(f)}] {f['text'][:60]}", file=sys.stderr)
            return
        targets = hits
    else:
        print("需要 --id 或 --query", file=sys.stderr)
        return

    now = datetime.now()
    ym = now.strftime("%Y-%m")
    grave_file = GRAVE / ym / f"facts-{ym}.jsonl"
    rel = str(grave_file.relative_to(ROOT))

    # 备份主库
    backup = FACTS.with_name(FACTS.name + ".bak-" + now.strftime("%Y%m%d-%H%M%S"))
    if FACTS.exists():
        backup.write_bytes(FACTS.read_bytes())

    # 追加进墓地
    grave_file.parent.mkdir(parents=True, exist_ok=True)
    with grave_file.open("a", encoding="utf-8") as f:
        for t in targets:
            f.write(json.dumps(t, ensure_ascii=False) + "\n")

    # 主库重写（去掉目标）
    target_ids = {fact_id(t) for t in targets}
    write_jsonl(FACTS, [f for f in facts if fact_id(f) not in target_ids])

    # 索引
    index = load_index()
    for t in targets:
        index.append(
            {
                "id": fact_id(t),
                "text": t.get("text", ""),
                "tags": t.get("tags", []),
                "ts": t.get("ts", ""),
                "moved_at": now.isoformat(timespec="seconds"),
                "file": rel,
                "reason": args.reason or "手动",
            }
        )
    save_index(index)

    print(f"已移入墓地 {len(targets)} 条（{rel}），主库备份 {backup.name}")
    for t in targets:
        print(f"  [{fact_id(t)}] {t['text'][:60]}")


def cmd_restore(args: argparse.Namespace) -> None:
    index = load_index()
    hit = [e for e in index if e.get("id") == args.id]
    if not hit:
        print(f"墓地里没有 id={args.id}（graveyard 命令可看列表）", file=sys.stderr)
        return
    entry = hit[0]
    grave_file = ROOT / entry["file"]
    rows = load_jsonl(grave_file)
    keep, back = [], []
    for r in rows:
        (back if fact_id(r) == args.id else keep).append(r)
    if not back:
        print("墓地文件里找不到正文（可能已焚毁）", file=sys.stderr)
        return

    # 墓地文件去掉该条
    write_jsonl(grave_file, keep)
    # 回主库（追加）
    with FACTS.open("a", encoding="utf-8") as f:
        for r in back:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    # 索引移除
    save_index([e for e in index if e.get("id") != args.id])

    print(f"已从墓地捞回 [{args.id}]：{back[0].get('text', '')[:60]}")


def cmd_graveyard(args: argparse.Namespace) -> None:
    index = load_index()
    if not index:
        print("墓地是空的")
        return
    print(f"墓地共 {len(index)} 条（不参与检索）：")
    for e in index[: args.limit]:
        reason = e.get("reason", "")
        print(f"[{e['id']}] {e.get('moved_at','')[:10]} {e.get('text','')[:70]}" + (f"  ({reason})" if reason else ""))


def main() -> None:
    p = argparse.ArgumentParser(description="四层记忆工具（含墓地）")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("search", help="按关键词检索事实")
    s.add_argument("query")
    s.add_argument("--limit", type=int, default=5)
    s.set_defaults(func=cmd_search)

    a = sub.add_parser("add", help="追加一条客观事实")
    a.add_argument("text")
    a.add_argument("--tags", default="")
    a.add_argument("--importance", type=int, choices=[1, 2, 3, 4, 5], default=None)
    a.set_defaults(func=cmd_add)

    h = sub.add_parser("handoff", help="打印常驻人格 + 交接 + 相关事实")
    h.add_argument("--query", default="")
    h.add_argument("--limit", type=int, default=5)
    h.set_defaults(func=cmd_handoff)

    st = sub.add_parser("stats", help="查看四层用量")
    st.set_defaults(func=cmd_stats)

    b = sub.add_parser("bury", help="把一条/多条事实移入墓地（不参与检索，可 restore）")
    b.add_argument("--id", default="")
    b.add_argument("--query", default="")
    b.add_argument("--all", action="store_true", help="query 命中多条时全部埋")
    b.add_argument("--reason", default="", help="移入原因")
    b.set_defaults(func=cmd_bury)

    r = sub.add_parser("restore", help="从墓地捞回一条事实")
    r.add_argument("id")
    r.set_defaults(func=cmd_restore)

    g = sub.add_parser("graveyard", help="列出墓地条目")
    g.add_argument("--limit", type=int, default=20)
    g.set_defaults(func=cmd_graveyard)

    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
