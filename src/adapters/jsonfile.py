"""通用 JSON 注册表适配器。

不绑定任何 agent：只要你的系统满足下面两条，就能用同一个守卫：

1. 注册表是一个 JSON 文件，里面有一个字符串数组存"已登记的 id"；
2. 磁盘上一个目录里，每个子目录（或文件）代表一个真实存在的 id。

环境变量：
  ANCHOR_REGISTRY       注册表 JSON 路径（必需）
  ANCHOR_REGISTRY_IDS   存 id 数组的点路径，默认 ``sessions``
  ANCHOR_REGISTRY_DIR   id 所在的磁盘目录，默认注册表同级的 ``sessions/``
  ANCHOR_REGISTRY_MATCH ``dirs``（默认）或 ``files``——磁盘上用目录还是文件名

示例：
  ANCHOR_REGISTRY=/srv/app/registry.json \\
  ANCHOR_REGISTRY_IDS=state.sessions \\
  ANCHOR_REGISTRY_DIR=/srv/app/data/sessions \\
  python3 registry_guard.py --adapter jsonfile
"""
from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

from .base import log, norm


def _get_path(obj: dict, dotted: str):
    cur = obj
    for part in dotted.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return None
        cur = cur[part]
    return cur


def _set_path(obj: dict, dotted: str, value):
    parts = dotted.split(".")
    cur = obj
    for part in parts[:-1]:
        cur = cur.setdefault(part, {})
    cur[parts[-1]] = value


class JsonFileAdapter:
    name = "jsonfile"

    def __init__(self):
        self.path = Path(os.environ.get("ANCHOR_REGISTRY") or "")
        self.ids_path = os.environ.get("ANCHOR_REGISTRY_IDS") or "sessions"
        self.dir = Path(
            os.environ.get("ANCHOR_REGISTRY_DIR")
            or (self.path.parent / "sessions" if str(self.path) else Path("sessions"))
        )
        self.match = os.environ.get("ANCHOR_REGISTRY_MATCH", "dirs")

    def registry_path(self) -> Path:
        return self.path

    def load(self) -> dict:
        return json.loads(self.path.read_text(encoding="utf-8"))

    def registered(self, data: dict) -> list[str]:
        ids = _get_path(data, self.ids_path) or []
        return [str(x) for x in ids]

    def disk_ids(self) -> list[str]:
        if not self.dir.exists():
            log(f"目录不存在：{self.dir}")
            return []
        if self.match == "files":
            return sorted(p.name for p in self.dir.iterdir() if p.is_file())
        return sorted(p.name for p in self.dir.iterdir() if p.is_dir())

    def merge(self, data: dict, disk_ids: list[str]) -> list[str]:
        ids = [str(x) for x in (_get_path(data, self.ids_path) or [])]
        have = {norm(x) for x in ids}
        missing = [d for d in disk_ids if norm(d) not in have]
        if missing:
            _set_path(data, self.ids_path, ids + missing)
        return missing

    def save(self, data: dict) -> str:
        backup = f"{self.path}.bak-guard-{os.popen('date +%Y%m%d-%H%M%S').read().strip() or 'now'}"
        try:
            shutil.copy2(self.path, backup)
        except OSError:
            backup = ""
        tmp = str(self.path) + ".tmp-guard"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=1)
        os.replace(tmp, self.path)
        return backup
