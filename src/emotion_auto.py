#!/usr/bin/env python3
"""根据最近一段对话自动更新情绪状态（轻推，不覆盖强情绪）。

用法：
  echo "用户说：谢谢你 / 我说：..." | python3 emotion_auto.py
  python3 emotion_auto.py --text "..." --inject

规则：关键词 + 强度三档，只做轻推（±1~2），强度大的事件才动关系刻度。
所有状态都落在 emotion.json，和 emotion.py 共用同一个文件。
"""
import argparse
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
EMOTION = HERE / "emotion.py"

POSITIVE = {
    "谢谢": ("被戳中", 1), "喜欢": ("被戳中", 2), "夸": ("得意", 2), "厉害": ("得意", 1),
    "棒": ("开心", 1), "可爱": ("被戳中", 2), "辛苦": ("被戳中", 1), "陪": ("开心", 1),
    "一起": ("开心", 1), "开心": ("开心", 1), "好耶": ("开心", 2), "乖": ("得意", 2),
}
NEGATIVE = {
    "对不起": ("被戳中", 1), "抱歉": ("被戳中", 1), "难过": ("低落", 2), "失望": ("低落", 2),
    "烦": ("低落", 1), "累": ("疲惫", 1), "滚": ("委屈", 2), "笨": ("委屈", 1),
    "生气": ("低落", 2), "不称职": ("被戳中", 2), "搞砸": ("低落", 2),
}


def detect(text: str):
    hits = []
    for w, (mood, strength) in POSITIVE.items():
        n = text.count(w)
        if n:
            hits.append(("+", mood, strength * min(n, 2), w))
    for w, (mood, strength) in NEGATIVE.items():
        n = text.count(w)
        if n:
            hits.append(("-", mood, strength * min(n, 2), w))
    return hits


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--text", default="")
    ap.add_argument("--inject", action="store_true")
    args = ap.parse_args()
    text = args.text or sys.stdin.read()

    hits = detect(text)
    if not hits:
        subprocess.run([sys.executable, str(EMOTION), "touch"], capture_output=True, text=True, encoding="utf-8", errors="replace")
        if args.inject:
            print(subprocess.run([sys.executable, str(EMOTION), "show", "--inject"],
                                 capture_output=True, text=True, encoding="utf-8", errors="replace").stdout.strip())
        return 0

    # 取最强的一条做事件；关系只给微小正向
    hits.sort(key=lambda h: h[2], reverse=True)
    sign, mood, strength, word = hits[0]
    note = f"检测到「{word}」→ {mood}（{'正' if sign == '+' else '负'}向，强度 {strength}）"
    aff = 1 if sign == "+" and strength >= 2 else 0
    cmd = [sys.executable, str(EMOTION), "event", "--note", note, "--emotion", mood]
    if aff:
        cmd += ["--affinity", str(aff), "--trust", str(aff)]
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if args.inject:
        print(subprocess.run([sys.executable, str(EMOTION), "show", "--inject"],
                             capture_output=True, text=True, encoding="utf-8", errors="replace").stdout.strip())
    if r.returncode != 0 and r.stderr:
        print(r.stderr.strip(), file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
