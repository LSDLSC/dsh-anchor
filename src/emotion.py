#!/usr/bin/env python3
"""情绪状态机 + 关系刻度：连续衰减 + 事件触发。

设计参考：
  - kokoro-chat 的 attitude 系统（affinity / trust 0-100 + 5 级关系阶段）
  - minecraft-ai-companion 的 Tempura 温度引擎（事件驱动、跨会话持久）
  - SillyTavern Character Moods（强度 / 概率 / 冷却，防止用力过猛）

和"每天线性 -1"的做法不同：
  - 强度用**指数衰减** I(t) = I0 * exp(-t / tau)，每种情绪有自己的 tau（兴奋退得快，难过留得慢）；
  - 事件按强度分三档：强事件覆盖、中事件混合、小事件轻推；
  - 冷却时间由事件强度算，不是固定 30 分钟。

用法：
  emotion.py show [--inject]   # 现算当前状态；--inject 输出一行可注入 prompt 的文本
  emotion.py set --mood 开心 --intensity 7 [--tau 0.4] [--cooldown 30]
  emotion.py event --affinity 3 --trust 1 --note "被夸了" [--emotion 被戳中]
  emotion.py touch             # 记一次对话
  emotion.py decay             # 结算：把现算强度写回基准（一般不用跑）

数据落在 $MEMORY_DIR/emotion.json（默认 $DSH_HOME/memory），单个 JSON 文件，可整体拷走。
注入文本里的称呼：ANCHOR_TARGET_NAME 优先，其次 emotion.json 的 "target" 字段，最后「对方」。
"""
from __future__ import annotations

import argparse
import json
import math
import os
import random
from datetime import datetime, timedelta
from pathlib import Path


def resolve_root() -> Path:
    """记忆目录：MEMORY_DIR → WHALE_MEMORY_DIR → 脚本上一级（像记忆库时）→ $DSH_HOME/memory。"""
    env = os.environ
    if env.get("MEMORY_DIR"):
        return Path(env["MEMORY_DIR"]).expanduser()
    if env.get("WHALE_MEMORY_DIR"):  # 旧变量名，兼容
        return Path(env["WHALE_MEMORY_DIR"]).expanduser()
    local = Path(__file__).resolve().parent.parent
    if (local / "facts.jsonl").exists() or (local / "hot.md").exists():
        return local
    return Path(os.environ.get("DSH_HOME") or Path.home() / ".dsh") / "memory"


ROOT = resolve_root()
STATE = ROOT / "emotion.json"

# 情绪标签，可改；改完 MOOD_TAU 里补上对应的时间常数即可
MOODS = ["开心", "平静", "疲惫", "低落", "害羞", "被戳中", "得意", "撒娇", "认真", "委屈"]

# 每种情绪的衰减时间常数（天）。兴奋退得快，难过留得久。
MOOD_TAU = {
    "开心": 0.4,
    "得意": 0.25,
    "被戳中": 0.6,
    "害羞": 0.5,
    "撒娇": 0.5,
    "认真": 0.8,
    "疲惫": 1.0,
    "低落": 1.0,
    "委屈": 1.0,
    "平静": 3.0,
}

POSITIVE = {"开心", "被戳中", "得意", "害羞", "撒娇"}
STAGES = [(0, "陌生"), (21, "熟悉"), (41, "亲近"), (61, "亲密"), (81, "家人")]

# 注入文本里怎么称呼对方：ANCHOR_TARGET_NAME > emotion.json 的 target 字段 > 「对方」
def target_name(state: dict | None = None) -> str:
    env = os.environ.get("ANCHOR_TARGET_NAME")
    if env:
        return env
    return str((state or {}).get("target") or "对方")


def now() -> datetime:
    return datetime.now()


def stamp(dt: datetime | None = None) -> str:
    return (dt or now()).strftime("%Y-%m-%d %H:%M")


def parse_ts(text: str | None) -> datetime | None:
    try:
        return datetime.strptime(text or "", "%Y-%m-%d %H:%M")
    except ValueError:
        return None


def stage_of(affinity: float) -> str:
    name = STAGES[0][1]
    for floor, label in STAGES:
        if affinity >= floor:
            name = label
    return name


def default_state() -> dict:
    return {
        "updated_at": stamp(),
        "last_chat": None,
        "mood": {"label": "平静", "intensity0": 3.0, "since": stamp(), "tau": 3.0, "cooldown_until": None},
        "relationship": {"affinity": 0, "trust": 0, "events": []},
    }


def load() -> dict:
    if not STATE.exists():
        s = default_state()
        save(s)
        return s
    try:
        s = json.loads(STATE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        s = default_state()
    s.setdefault("mood", {})
    s.setdefault("relationship", {})
    s["relationship"].setdefault("events", [])
    m = s["mood"]
    if "intensity0" not in m:  # 兼容旧格式的 intensity 字段
        m["intensity0"] = float(m.pop("intensity", 3))
        m["tau"] = MOOD_TAU.get(m.get("label", "平静"), 3.0)
    return s


def save(s: dict) -> None:
    s["updated_at"] = stamp()
    ROOT.mkdir(parents=True, exist_ok=True)
    backup = STATE.with_name(STATE.name + ".bak")
    try:
        if STATE.exists():
            backup.write_bytes(STATE.read_bytes())
    except OSError:
        pass
    tmp = STATE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(s, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(STATE)


def time_bonus(at: datetime | None = None) -> float:
    """时段基线：夜里更精神、清晨没睡醒、白天平常。可按角色作息改。"""
    h = (at or now()).hour
    if h >= 22 or h < 3:
        return 1.5
    if h < 6:
        return 0.5
    if h < 9:
        return -1.0
    if h < 18:
        return 0.0
    return 0.5


def current_intensity(mood: dict, at: datetime | None = None) -> float:
    """指数衰减 + 时段加成 + 确定性随机回潮（每 15 分钟一个种子，不抖屏）。"""
    at = at or now()
    since = parse_ts(mood.get("since"))
    if not since:
        return float(mood.get("intensity0", 0))
    tau = float(mood.get("tau") or MOOD_TAU.get(mood.get("label", "平静"), 3.0))
    hours = max((at - since).total_seconds() / 3600.0, 0.0)
    base = float(mood.get("intensity0", 0)) * math.exp(-hours / (tau * 24.0))
    seed = int(at.timestamp() // 900)
    noise = random.Random(seed).gauss(0.0, 0.4)
    return max(0.0, min(10.0, base + time_bonus(at) + noise))


def effective_mood(s: dict) -> tuple[str, float]:
    mood = s["mood"]
    i = current_intensity(mood)
    label = mood.get("label", "平静")
    if i < 0.5:  # 退到基线以下就回到平静
        return "平静", max(i, 0.0)
    return label, i


def inject_line(s: dict) -> str:
    label, inten = effective_mood(s)
    rel = s["relationship"]
    aff = rel.get("affinity", 0)
    extra = ""
    last = parse_ts(s.get("last_chat"))
    if last:
        gap = (now() - last).total_seconds() / 3600
        if gap >= 72:
            extra = f"；已经 {int(gap // 24)} 天没聊了"
        elif gap >= 24:
            extra = "；昨天之后就没聊过"
    cd = ""
    until = parse_ts(s["mood"].get("cooldown_until"))
    if until and until > now():
        cd = f"；强情绪冷却到 {until.strftime('%H:%M')}"
    return (
        f"[心情] {label}（强度 {inten:.1f}/10）{cd}；"
        f"对{target_name(s)}：{stage_of(aff)}（亲密 {aff:.0f}/100，信任 {rel.get('trust', 0):.0f}）{extra}"
    )


def cmd_show(args: argparse.Namespace) -> None:
    s = load()
    if args.inject:
        print(inject_line(s))
        return
    label, inten = effective_mood(s)
    mood = s["mood"]
    rel = s["relationship"]
    print(f"心情：{label}（现算强度 {inten:.1f}/10；基准 {mood.get('intensity0')}/10，τ={mood.get('tau')} 天，自 {mood.get('since')}）")
    if mood.get("cooldown_until"):
        print(f"  强情绪冷却至：{mood['cooldown_until']}")
    print(f"关系：{stage_of(rel.get('affinity', 0))}（亲密 {rel.get('affinity', 0):.0f}/100，信任 {rel.get('trust', 0):.0f}/100）")
    print(f"上次对话：{s.get('last_chat') or '（无记录）'}")
    evs = rel.get("events", [])[-5:]
    if evs:
        print("最近事件：")
        for e in evs:
            print(f"  {e.get('at')}  {e.get('note')}  (亲密 {e.get('affinity', 0):+g}，信任 {e.get('trust', 0):+g}，{e.get('mode', '')})")


def pick_emotion(note: str, sign: int) -> str:
    if sign >= 0:
        for key, emo in (("夸", "被戳中"), ("厉害", "得意"), ("棒", "得意"), ("谢谢", "被戳中"),
                         ("喜欢", "害羞"), ("可爱", "害羞"), ("帮", "开心"), ("一起", "开心"), ("好笑", "开心")):
            if key in note:
                return emo
        return "开心"
    for key, emo in (("骂", "委屈"), ("冷落", "低落"), ("错", "低落"), ("凶", "委屈")):
        if key in note:
            return emo
    return "低落"


def cmd_set(args: argparse.Namespace) -> None:
    s = load()
    if args.mood not in MOODS:
        raise SystemExit(f"心情只能是：{'、'.join(MOODS)}")
    inten = max(0.0, min(10.0, args.intensity))
    tau = args.tau if args.tau and args.tau > 0 else MOOD_TAU.get(args.mood, 3.0)
    s["mood"] = {"label": args.mood, "intensity0": inten, "since": stamp(), "tau": tau, "cooldown_until": None}
    if args.cooldown > 0:
        s["mood"]["cooldown_until"] = stamp(now() + timedelta(minutes=args.cooldown))
    s["last_chat"] = stamp()
    save(s)
    print(f"已设为：{args.mood}（基准 {inten:g}/10，τ={tau} 天）")


def cmd_event(args: argparse.Namespace) -> None:
    s = load()
    rel = s["relationship"]
    # 事件强度 0-10：取关系变化的最大项
    strength = max(abs(args.affinity), abs(args.trust))
    sign = 1 if (args.affinity + args.trust) >= 0 else -1
    if sign < 0:  # 乐观偏置：负面事件打个折
        strength *= 0.7
    cur_label, cur_inten = effective_mood(s)
    new_label = args.emotion or pick_emotion(args.note, sign)
    if new_label not in MOODS:
        new_label = "开心" if sign > 0 else "低落"

    tau = MOOD_TAU.get(new_label, 3.0)
    if strength >= 6:  # 强事件：覆盖，但不满格（留 1 分余地）
        base = min(9.0, 5.0 + strength * 0.5) if sign > 0 else min(7.0, 3.0 + strength * 0.4)
        mode = "覆盖"
        s["mood"] = {"label": new_label, "intensity0": round(base, 1), "since": stamp(), "tau": tau,
                     "cooldown_until": stamp(now() + timedelta(minutes=int(20 + 10 * strength)))}
    elif strength >= 3:  # 中事件：混合，旧情绪打折
        base = max(cur_inten * 0.5, strength * 0.8)
        mode = "混合"
        s["mood"] = {"label": new_label, "intensity0": round(base, 1), "since": stamp(), "tau": tau,
                     "cooldown_until": None}
    else:  # 小事件：轻推，不重置时间轴，也不加冷却
        base = max(0.0, min(10.0, cur_inten + (1.0 if sign > 0 else -0.5)))
        mode = "轻推"
        if cur_label == "平静" and base >= 2:
            s["mood"]["label"] = new_label
            s["mood"]["tau"] = MOOD_TAU.get(new_label, 3.0)
        s["mood"]["intensity0"] = round(base, 1)

    rel["affinity"] = max(0, min(100, rel.get("affinity", 0) + args.affinity))
    rel["trust"] = max(0, min(100, rel.get("trust", 0) + args.trust))
    rel.setdefault("events", []).append({
        "at": stamp(), "note": args.note, "affinity": args.affinity, "trust": args.trust,
        "mode": mode, "emotion": new_label,
    })
    rel["events"] = rel["events"][-30:]
    s["last_chat"] = stamp()
    save(s)
    print(f"事件：{args.note}（强度 {strength:g} → {mode}为 {new_label} 基准 {base:.1f}/10，τ={tau} 天）")
    print(f"  亲密 {args.affinity:+g} → {rel['affinity']:.0f}，信任 {args.trust:+g} → {rel['trust']:.0f}")


def cmd_touch(args: argparse.Namespace) -> None:
    s = load()
    s["last_chat"] = stamp()
    save(s)
    print(f"已记一次对话：{s['last_chat']}")


def cmd_decay(args: argparse.Namespace) -> None:
    """结算：把现算强度写回基准并重置起点（一般不用跑，show 已经现算）。"""
    s = load()
    label, inten = effective_mood(s)
    s["mood"]["intensity0"] = round(inten, 1)
    s["mood"]["since"] = stamp()
    if label == "平静":
        s["mood"]["label"] = "平静"
        s["mood"]["tau"] = 3.0
    save(s)
    print(f"已结算：{label} {inten:.1f}/10")


def main() -> None:
    p = argparse.ArgumentParser(description="情绪状态机（连续衰减 + 事件触发）")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("show", help="查看现算状态")
    s.add_argument("--inject", action="store_true", help="只输出一行可注入文本")
    s.set_defaults(func=cmd_show)

    st = sub.add_parser("set", help="设置心情（基准值）")
    st.add_argument("--mood", required=True)
    st.add_argument("--intensity", type=float, default=5.0)
    st.add_argument("--tau", type=float, default=None, help="衰减时间常数（天），默认按情绪查表")
    st.add_argument("--cooldown", type=int, default=0, help="强情绪冷却分钟数")
    st.set_defaults(func=cmd_set)

    ev = sub.add_parser("event", help="记录影响关系的事件")
    ev.add_argument("--affinity", type=float, default=0)
    ev.add_argument("--trust", type=float, default=0)
    ev.add_argument("--note", required=True)
    ev.add_argument("--emotion", default=None, help="指定新情绪（默认按正负与关键词推）")
    ev.set_defaults(func=cmd_event)

    tc = sub.add_parser("touch", help="记一次对话")
    tc.set_defaults(func=cmd_touch)

    d = sub.add_parser("decay", help="把现算强度结算回基准")
    d.set_defaults(func=cmd_decay)

    args = p.parse_args()
    func = getattr(args, "func", None)
    if func is None:
        p.print_help()
        return
    func(args)


if __name__ == "__main__":
    main()
