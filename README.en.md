# Anchor · a memory anchor for companion AI

[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![Zero dependencies](https://img.shields.io/badge/dependencies-0-success.svg)](src/memory.py)

> Remember what should be remembered, forget what should be forgotten, and recover what was lost.

**For anyone building long-term memory into their own agent**: one directory plus one `memory.py` is enough to layer your agent's *facts / episodes / persona*; anything you don't want to remember moves into a graveyard — not destroyed, not lost, restorable at any time. Pure standard library, no database, no daemon, runs fine on a 2-core 4 GB box.

Anchor grew out of real failures: a session registry overwritten by a second host process, memory existing in a single copy, a persona diluted by time, old context crowding out the prompt. It is not "yet another memory plugin" — it treats **reliability** as the first requirement: don't lose data first, be smart second.

**Two cores**: a cross-session long-term memory store (layered `facts / journal / soul`) and a physical forgetting graveyard (moved out of retrieval, never destroyed, `restore`-able). This is the part we most want to share — we learned it from ACT-R, MemoryOS and YourMemory and stitched their ideas into something that runs on a 2C4G machine.

Pure Python / Node standard library, zero dependencies. DSH is the first adapter, not the only target.

---

## 60-second tour

An agent that forgets everything between sessions is usually saved by three things: a **fact store** (it remembers), a **persona anchor** (it stays itself), and a **forgetting mechanism** (it doesn't drown in old clutter). This repo packs all three into one directory plus a few scripts:

```
$MEMORY_DIR/
├── hot.md                  rules injected every turn (L1 resident)
├── facts.jsonl             one searchable fact per line (L2 facts)
├── journal/                session digests, one file per day (L3 episodes)
├── state.json              where we left off / what is next (L4 handoff)
├── soul/soul.md            identity, relationship, red lines (never forgotten)
├── emotion.json            mood + relationship scale (time-decayed)
└── graveyard/              moved out of retrieval, kept on disk, restorable
    ├── index.json
    └── 2026-11/facts-2026-11.jsonl
```

Four commands are enough to start:

```bash
export MEMORY_DIR="$HOME/.dsh/memory"
python3 src/memory.py add "user prefers conclusions first" --tags preference --importance 4
python3 src/memory.py search conclusion
python3 src/memory.py handoff          # what to read at boot: soul → hot → state → hits
python3 src/memory.py bury --id <id>   # stop recalling it, but don't delete it
```

No database, no daemon, no network calls. **The directory is the whole state** — copy it and you have a backup.

---

## Memory model (the small version)

### Four layers, split by "should it be cleaned up", not by "how important"

| Layer | File | Cleaned up? |
|---|---|---|
| L1 resident rules | `hot.md` | hand-edited only |
| L2 facts | `facts.jsonl` | decays, can be buried, restorable |
| L3 episodes | `journal/*.md` | compressed/archived, not deleted |
| L4 handoff | `state.json` | overwritten each time |
| Persona | `soul/soul.md` | **never** — outside the forgetting system |

### A fact is one JSON line

```json
{"id":"a1b2c3d4","ts":"2026-11-20T10:00:00+08:00","text":"user prefers conclusions first",
 "tags":["preference"],"importance":4,"access_times":[1795000000,1795100000]}
```

### Forgetting: ACT-R activation, not expiry

Each fact gets a decaying activation score from its access history:

```
B = ln( Σ (t_j + 1)^-0.5 )        # base-level, older/seldom-used → colder
A = B + 0.4 × importance + ε       # ε = N(0, 0.3), a little noise
P = σ(A - τ)                       # probability of being recalled
```

No hard thresholds, no "delete after 30 days". Frequently used facts get recalled more often (retrieval is rehearsal: every hit appends to `access_times`, capped at the last 20); rarely used ones sink but stay on disk.

### Deletion has three levels, tombstone first

1. **Down-weight** — reversible; just let activation decay.
2. **Bury** — move to `graveyard/`, out of retrieval, still on disk, `restore` brings it back.
3. **Destroy** — explicit, human-approved, then the record is actually removed.

### Why the persona layer doesn't forget

`soul.md` is not part of the forgetting system: set to 444, never decayed, never moved to the graveyard, only changed by a human. Whatever else is forgotten, the answers to "who am I" and "who am I to you" load first.

---

## Commands

```bash
python3 src/memory.py add <text> [--tags a,b] [--importance 1-5]
python3 src/memory.py search <keyword>
python3 src/memory.py handoff
python3 src/memory.py bury --id <id> | --query <keyword> [--all] [--reason r]
python3 src/memory.py restore <id>
python3 src/memory.py graveyard
python3 src/activation.py score [--top N] [--tau -1.5]
python3 src/activation.py tick <id>
python3 src/anchor.py status      # scheduled-task health
python3 src/anchor.py check       # env/path/deps/data self-check
python3 src/registry_guard.py --adapter dsh
```

---

## Install

**One line (recommended)** — Linux / macOS:

```bash
curl -fsSL https://raw.githubusercontent.com/LSDLSC/dsh-anchor/main/quickstart/bootstrap.sh | bash
# China mirror (self-signed cert):
curl -fsSLk https://47.111.65.201:8080/sites/hub/anchor/install.sh | bash
```

**Memory only, no host integration**:

```bash
curl -fsSLk -O https://47.111.65.201:8080/sites/hub/anchor/anchor-src-0.1.0.tar.gz
tar xzf anchor-src-0.1.0.tar.gz && cd anchor-src-0.1.0
MEMORY_DIR=~/.anchor/memory python3 src/memory.py add "hello"
```

**systemd (7×24)** and **Docker** variants live in `deploy/` and `docker/`.

---

## Adapters

Anchor's core knows nothing about DSH. A host is plugged in through a thin adapter:

| Adapter | What it does |
|---|---|
| `dsh` | reads/writes DSH's `workspace.json` session registry, unions on-disk session dirs |
| `jsonfile` | any host that can name a registry file + a directory of IDs |

A custom adapter implements five methods: `load()`, `registered()`, `disk_ids()`, `merge()`, `save()`. See `src/adapters/base.py`.

---

## Known limitations

See [docs/limitations.md](docs/limitations.md). Short list: the lock cannot stop a host that rewrites blindly; a timer window still exists; no test suite/CI yet; keyword search, not embeddings; parameter values (decay, thresholds) are empirical; tested on Linux only.

---

## Credits

Ideas borrowed from: ACT-R (base-level activation), MemoryOS (EMNLP 2025, layered memory), YourMemory (decay formula + consolidation), Zep/Graphiti (bitemporal invalidation), Letta (core/archival memory). See `docs/architecture.md`.

## License

MIT. See [LICENSE](LICENSE).
