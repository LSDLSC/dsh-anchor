#!/usr/bin/env python3
"""把记忆库渲染成一个本地总览页，不用逐个翻文件。

用法：
  python3 src/memory_view.py                 # 生成到 $MEMORY_DIR/memory-view.html
  python3 src/memory_view.py --out /tmp/x.html
  MEMORY_DIR=/path/to/memory python3 src/memory_view.py

只读：不改任何记忆文件，不联网。
"""
from __future__ import annotations

import argparse
import html
import json
import os
from pathlib import Path


def resolve_root() -> Path:
    env = os.environ
    if env.get("MEMORY_DIR"):
        return Path(env["MEMORY_DIR"]).expanduser()
    if env.get("WHALE_MEMORY_DIR"):  # 旧变量，兼容
        return Path(env["WHALE_MEMORY_DIR"]).expanduser()
    home = Path(env.get("DSH_HOME") or Path.home() / ".dsh")
    return home / "memory"


ROOT = resolve_root()


def read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return ""


def main() -> None:
    ap = argparse.ArgumentParser(description="渲染记忆总览页")
    ap.add_argument("--out", default=None, help="输出文件，默认 $MEMORY_DIR/memory-view.html")
    ap.add_argument("--root", default=None, help="记忆目录，默认取 MEMORY_DIR")
    args = ap.parse_args()

    root = Path(args.root).expanduser() if args.root else ROOT
    out = Path(args.out).expanduser() if args.out else root / "memory-view.html"

    hot = read(root / "hot.md")
    state_raw = read(root / "state.json")
    try:
        state = json.loads(state_raw) if state_raw else {}
    except json.JSONDecodeError:
        state = {"_error": "state.json 解析失败"}

    facts = []
    for line in read(root / "facts.jsonl").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            facts.append(json.loads(line))
        except json.JSONDecodeError:
            facts.append({"text": line, "tags": ["解析失败"]})

    journals = []
    for p in sorted((root / "journal").glob("*.md")):
        journals.append({"name": p.name, "text": read(p)[:4000]})

    # 墓地：graveyard/index.json 是索引，条目正文按月份落在 graveyard/YYYY-MM/*.jsonl
    grave = []
    index_raw = read(root / "graveyard" / "index.json")
    try:
        index = json.loads(index_raw) if index_raw else []
    except json.JSONDecodeError:
        index = []
    seen_files = set()
    for row in (index if isinstance(index, list) else []):
        f = row.get("file") if isinstance(row, dict) else None
        if not f or f in seen_files:
            continue
        seen_files.add(f)
        for line in read(root / f).splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                grave.append(json.loads(line))
            except json.JSONDecodeError:
                pass

    def esc(x: object) -> str:
        return html.escape(str(x))

    fact_html = "\n".join(
        f'<article class="card fact" data-text="{esc(f.get("text", ""))}">'
        f'<div class="meta">{esc(f.get("ts", ""))} · {esc(" / ".join(f.get("tags", [])))}'
        f'{" · 重要度 " + esc(f.get("importance")) if f.get("importance") else ""}</div>'
        f'<p>{esc(f.get("text", ""))}</p></article>'
        for f in reversed(facts)
    ) or "<p class='muted'>还没有事实条目。</p>"
    journal_html = "\n".join(
        f'<details class="journal" data-text="{esc(j["name"] + " " + j["text"])}">'
        f'<summary>{esc(j["name"])}</summary><pre>{esc(j["text"])}</pre></details>'
        for j in journals
    ) or "<p class='muted'>还没有 journal。</p>"
    grave_html = "".join(
        f'<article class="card grave" data-text="{esc(g.get("text", ""))}">'
        f'<div class="meta">{esc(g.get("ts", ""))} · 墓地</div><p>{esc(g.get("text", ""))}</p></article>'
        for g in reversed(grave)
    )

    out.write_text(
        f"""<!doctype html>
<html lang="zh-CN"><meta charset="utf-8">
<title>记忆总览</title>
<style>
:root{{--bg:#f4f7fb;--card:#fff;--ink:#17202b;--muted:#667085;--line:#dbe3ee;--accent:#2563eb}}
*{{box-sizing:border-box}} body{{margin:0;background:var(--bg);color:var(--ink);font:14px/1.65 system-ui,-apple-system,"Segoe UI",sans-serif}}
main{{max-width:980px;margin:0 auto;padding:28px 18px 60px}}
h1{{font-size:24px;margin:0 0 6px}} h2{{font-size:16px;margin:26px 0 10px}}
.muted{{color:var(--muted)}} .top{{display:flex;gap:12px;flex-wrap:wrap;align-items:center;justify-content:space-between}}
.stats{{display:flex;gap:8px;flex-wrap:wrap}} .pill{{background:#e8efff;color:#1d4ed8;border-radius:999px;padding:4px 10px;font-size:12px}}
.card{{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:14px 16px;margin:10px 0}}
.card p{{margin:6px 0 0}} .meta{{color:var(--muted);font-size:12px}}
.hot{{white-space:pre-wrap}} pre{{white-space:pre-wrap;word-break:break-word;margin:8px 0 0;font:13px/1.6 ui-monospace,Consolas,monospace}}
details{{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:10px 14px;margin:8px 0}}
summary{{cursor:pointer;font-weight:600}}
input{{width:100%;padding:12px 14px;border:1px solid var(--line);border-radius:12px;font:inherit;background:#fff}}
</style>
<main>
<div class="top"><div><h1>记忆总览</h1><div class="muted">四层记忆：常驻规则 / 事实 / 经历 / 交接</div></div>
<div class="stats"><span class="pill">常驻 {len(hot)} 字</span><span class="pill">事实 {len(facts)} 条</span><span class="pill">经历 {len(journals)} 篇</span><span class="pill">墓地 {len(grave)} 条</span></div></div>
<input id="q" placeholder="搜事实、标签、经历…">
<h2>L1 常驻层 · hot.md</h2><div class="card hot">{esc(hot)}</div>
<h2>L4 交接 · state.json</h2><div class="card"><pre>{esc(json.dumps(state, ensure_ascii=False, indent=2))}</pre></div>
<h2>L2 事实层 · facts.jsonl</h2>{fact_html}
<h2>L3 经历层 · journal/</h2>{journal_html}
<h2>墓地 · graveyard/（不参与检索，可 restore）</h2>{grave_html or "<p class='muted'>墓地是空的。</p>"}
</main>
<script>
const q=document.getElementById('q');
q.addEventListener('input',()=>{{
  const t=q.value.trim().toLowerCase();
  document.querySelectorAll('[data-text]').forEach(el=>{{
    el.style.display=!t||el.dataset.text.toLowerCase().includes(t)?'':'none';
  }});
}});
</script>
</html>
""",
        encoding="utf-8",
    )
    print(f"已生成 {out}（{out.stat().st_size} 字节）")


if __name__ == "__main__":
    main()
