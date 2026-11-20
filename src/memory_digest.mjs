#!/usr/bin/env node
// 记忆自动沉淀 —— 把最近 N 小时的会话原文，抽成可读的日志 + 沉淀候选
// 用法: node memory-digest.mjs [小时数=24] [--dry]
// 输出: <DSH_HOME>/memory/journal/YYYY-MM-DD-session-xxxxxxxx.md
// 设计原则: 只读会话文件，不改任何东西；不写入 memo（memo 由本人在会话里决定写入）

import fs from "node:fs"
import path from "node:path"
import zlib from "node:zlib"

const HOME = process.env.USERPROFILE || process.env.HOME
const DSH = process.env.DSH_HOME || path.join(HOME, ".dsh")
const SESS_ROOT = path.join(DSH, "sessions")
const JOURNAL = path.join(process.env.MEMORY_DIR || path.join(DSH, "memory"), "journal")
const HOURS = Number(process.argv[2] || 24)
const DRY = process.argv.includes("--dry")
const MAGIC = Buffer.from([0x28, 0xb5, 0x2f, 0xfd])

// —— 只保留真正来自人的发言，过滤掉系统注入的通知 ——
const NOISE_SOURCES = new Set([
  "user-approval",
  "tool-registry",
  "sandbox-notice",
])

// —— 值得沉淀的信号词 ——
const SIGNALS = [
  "记住", "以后", "从现在起", "一直", "我的", "我是", "我不能", "我不要",
  "必须", "别再", "不要再", "规则", "偏好", "习惯", "决定", "定调",
  "预算", "密码", "账号", "服务器", "插件", "记忆",
]

function decodeFrames(buf) {
  const starts = []
  let idx = 0
  while (true) {
    const i = buf.indexOf(MAGIC, idx)
    if (i < 0) break
    starts.push(i)
    idx = i + 4
  }
  const parts = []
  for (let k = 0; k < starts.length; k++) {
    const s = starts[k]
    const e = k + 1 < starts.length ? starts[k + 1] : buf.length
    try {
      parts.push(zlib.zstdDecompressSync(buf.subarray(s, e)).toString("utf8"))
    } catch {
      // 单帧坏掉不影响其余
    }
  }
  return parts.join("")
}

function textOf(content) {
  if (typeof content === "string") return content
  if (!Array.isArray(content)) return ""
  return content
    .filter((c) => c && c.type === "text" && typeof c.text === "string")
    .map((c) => c.text)
    .join("\n")
}

// —— 宿主注入的伪“用户消息”，一律跳过 ——
const INJECT_PREFIX = [
  "Current runtime context",
  "Time sampled",
  "<system-reminder>",
  "background job ",
  "[bili]",
  "Updated instructions from",
]

function isInjected(text) {
  const t = String(text || "").trimStart()
  return INJECT_PREFIX.some((p) => t.startsWith(p))
}

// —— 脱敏：密码 / AccessKey / API Key / token 一律打码，绝不写进日志 ——
const SECRET_RULES = [
  [/(密码|口令|passwd|password)\s*(是|为|:|：|=)?\s*[\x21-\x7e]{4,}/gi, "$1=***"],
  [/sk-[A-Za-z0-9_-]{10,}/g, "sk-***"],
  [/LTAI[A-Za-z0-9]{10,}/g, "LTAI***"],
  [/(secret|token|apikey|api_key)\s*(是|为|:|：|=)?\s*[A-Za-z0-9_-]{12,}/gi, "$1=***"],
  [/[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}/g, "<邮箱已隐去>"],
]

function redact(text) {
  let s = String(text || "")
  for (const [re, rep] of SECRET_RULES) s = s.replace(re, rep)
  return s
}

function clip(s, n) {
  const t = redact(String(s || "")).replace(/\s+/g, " ").trim()
  return t.length <= n ? t : t.slice(0, n) + "…"
}

function walk(dir, out = []) {
  let ents = []
  try {
    ents = fs.readdirSync(dir, { withFileTypes: true })
  } catch {
    return out
  }
  for (const e of ents) {
    const p = path.join(dir, e.name)
    if (e.isDirectory()) walk(p, out)
    else if (e.name === "session.v4.jsonl.zstd") out.push(p)
  }
  return out
}

function digestOne(file, cutoff) {
  const buf = fs.readFileSync(file)
  const objs = decodeFrames(buf)
    .split("\n")
    .filter(Boolean)
    .map((l) => {
      try {
        return JSON.parse(l)
      } catch {
        return null
      }
    })
    .filter(Boolean)

  const meta = objs.find((o) => o.type === "session") || {}
  const title = (objs.find((o) => o.type === "session/title") || {}).data?.title || "（无标题）"

  const userMsgs = []
  const assistantMsgs = []
  for (const o of objs) {
    const t = o.time || 0
    if (t && t < cutoff) continue
    if (o.type === "user/message") {
      const src = o.data?.source?.kind
      if (src && NOISE_SOURCES.has(src)) continue
      const txt = textOf(o.data?.content)
      if (txt && !isInjected(txt)) userMsgs.push({ time: t, text: txt })
    } else if (o.type === "assistant/message") {
      const txt = textOf(o.data?.message?.content)
      if (txt) assistantMsgs.push({ time: t, text: txt, turn: o.data?.turn })
    }
  }
  if (!userMsgs.length && !assistantMsgs.length) return null

  const candidates = []
  for (const m of userMsgs) {
    const hits = SIGNALS.filter((k) => m.text.includes(k))
    if (hits.length) candidates.push({ time: m.time, hits, text: clip(m.text, 240) })
  }

  const fmt = (ms) =>
    ms ? new Date(ms).toLocaleString("zh-CN", { hour12: false }) : "?"

  const lines = []
  lines.push(`# 会话摘要 · ${title}`)
  lines.push("")
  lines.push(`- 会话 ID：\`${meta.id || path.basename(path.dirname(file))}\``)
  lines.push(`- 工作区：\`${meta.cwd || "?"}\``)
  lines.push(`- 时间范围：${fmt(Math.min(...[...userMsgs, ...assistantMsgs].map((m) => m.time)))} → ${fmt(Math.max(...[...userMsgs, ...assistantMsgs].map((m) => m.time)))}`)
  lines.push(`- 消息数：用户 ${userMsgs.length} / 助手 ${assistantMsgs.length}`)
  lines.push("")
  lines.push("## 用户诉求（原文截断）")
  lines.push("")
  for (const m of userMsgs) lines.push(`- ${clip(m.text, 260)}`)
  lines.push("")
  lines.push("## 助手结论（每轮首句）")
  lines.push("")
  const seen = new Set()
  for (const m of assistantMsgs) {
    const key = m.turn ?? m.time
    if (seen.has(key)) continue
    seen.add(key)
    const first = m.text.split(/\n/).map((s) => s.trim()).filter(Boolean)[0] || ""
    if (first) lines.push(`- ${clip(first, 200)}`)
  }
  lines.push("")
  if (candidates.length) {
    lines.push("## 可沉淀候选（命中信号词，待本人确认后写 memo）")
    lines.push("")
    for (const c of candidates) lines.push(`- [${c.hits.join("/")}] ${c.text}`)
    lines.push("")
  }
  return { title, id: meta.id, md: lines.join("\n"), userCount: userMsgs.length, candCount: candidates.length }
}

function main() {
  const cutoff = Date.now() - HOURS * 3600 * 1000
  const files = walk(SESS_ROOT).filter((f) => {
    try {
      return fs.statSync(f).mtimeMs >= cutoff
    } catch {
      return false
    }
  })
  if (!files.length) {
    console.log(`最近 ${HOURS} 小时没有活跃会话文件`)
    return
  }
  if (!DRY && !fs.existsSync(JOURNAL)) fs.mkdirSync(JOURNAL, { recursive: true })
  let n = 0
  let cands = 0
  for (const f of files) {
    const r = digestOne(f, cutoff)
    if (!r) continue
    const day = new Date().toISOString().slice(0, 10)
    const rawId = String(r.id || path.basename(path.dirname(f))).replace(/^session-/, "")
    const short = rawId.slice(0, 8)
    const out = path.join(JOURNAL, `${day}-session-${short}.md`)
    if (!DRY) fs.writeFileSync(out, r.md, "utf8")
    n++
    cands += r.candCount
    console.log(`  ${path.basename(out)}  用户${r.userCount}条 候选${r.candCount}条  <- ${r.title}`)
  }
  console.log(`完成：${n} 个会话，沉淀候选合计 ${cands} 条${DRY ? "（dry-run，未写文件）" : "，已写入 " + JOURNAL}`)
}

main()
