"""DSH 适配器。

DSH 的会话列表只认 ``<DSH_HOME>/storages/workspace.json`` 的
``tables.workspaces[].sessionIds``，不扫 ``sessions/`` 目录。
这个适配器负责：读这份注册表、修 ``updatedAt`` 的数字时间戳、
把磁盘上未登记的会话目录并进去。
"""
from __future__ import annotations

import glob
import json
import os
import shutil
from pathlib import Path

from .base import iso_of, log, norm

DSH_HOME = Path(os.environ.get("DSH_HOME") or Path.home() / ".dsh")


class DshAdapter:
    name = "dsh"

    def __init__(self, home: Path | None = None):
        self.home = Path(home) if home else DSH_HOME

    # -- 路径 -------------------------------------------------------------
    def registry_path(self) -> Path:
        return self.home / "storages" / "workspace.json"

    def session_dir_of(self, workspace_path: str | None) -> Path | None:
        """把工作区路径编码成 sessions 目录名（DSH 的 ``--path--`` 规则）。"""
        if not workspace_path:
            return None
        try:
            p = Path(workspace_path).resolve()
        except OSError:
            return None
        slug = "--" + str(p).lstrip("/\\").replace("\\", "-").replace("/", "-").replace(":", "") + "--"
        return self.home / "sessions" / slug

    # -- 读 ---------------------------------------------------------------
    def load(self) -> dict:
        data = json.loads(self.registry_path().read_text(encoding="utf-8"))
        for ws in self._workspaces(data):
            ua = ws.get("updatedAt")
            if isinstance(ua, (int, float)) and not isinstance(ua, bool):
                iso = iso_of(ua)
                ws["updatedAt"] = iso
                log(f"updatedAt 数字已修正：{ua} -> {iso}")
        return data

    @staticmethod
    def _workspaces(data: dict) -> list[dict]:
        workspaces = data.get("tables", {}).get("workspaces")
        if not workspaces:
            return []
        return list(workspaces.values()) if isinstance(workspaces, dict) else list(workspaces)

    def registered(self, data: dict) -> list[str]:
        out: list[str] = []
        for ws in self._workspaces(data):
            out.extend(ws.get("sessionIds") or [])
        return out

    def disk_ids(self) -> list[str]:
        ws = self._workspaces(self.load())[:1]
        if not ws:
            return []
        sess_dir = self.session_dir_of(ws[0].get("path"))
        if sess_dir is None or not sess_dir.exists():
            log(f"会话目录不存在：{sess_dir}")
            return []
        return sorted(os.path.basename(p) for p in glob.glob(str(sess_dir / "*")) if os.path.isdir(p))

    # -- 写 ---------------------------------------------------------------
    def merge(self, data: dict, disk_ids: list[str]) -> list[str]:
        ws = self._workspaces(data)
        if not ws:
            return []
        target = ws[0]
        ids = list(target.get("sessionIds") or [])
        have = {norm(x) for x in ids}
        missing = [d for d in disk_ids if norm(d) not in have]
        if missing:
            target["sessionIds"] = ids + missing
        return missing

    def save(self, data: dict) -> str:
        p = self.registry_path()
        backup = f"{p}.bak-guard-{os.popen('date +%Y%m%d-%H%M%S').read().strip() or 'now'}"
        try:
            shutil.copy2(p, backup)
        except OSError:
            backup = ""
        tmp = str(p) + ".tmp-guard"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
        os.replace(tmp, p)
        return backup
