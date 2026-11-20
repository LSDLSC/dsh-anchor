#!/usr/bin/env python3
"""通用注册表守护（与具体 agent 解耦）。

流程与 DSH 无关：
  锁 -> 读注册表（顺带修格式）-> 读磁盘上的真实 id -> 并集合并
     -> 写前重读再合并（防宿主覆盖）-> 写回（带备份）-> 写结果 -> 可选重启

适配器：
  --adapter dsh        DSH 的 workspace.json + sessions/（默认）
  --adapter jsonfile   任意 JSON 注册表（见 adapters/jsonfile.py 的环境变量）

用法：
  DSH_HOME=/home/user/.dsh python3 registry_guard.py
  ANCHOR_REGISTRY=/srv/app/registry.json python3 registry_guard.py --adapter jsonfile
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from adapters.base import file_lock, log, norm, write_result  # noqa: E402
from adapters.dsh import DshAdapter  # noqa: E402
from adapters.jsonfile import JsonFileAdapter  # noqa: E402


def make_adapter(name: str, home: Path | None = None):
    if name == "jsonfile":
        return JsonFileAdapter()
    return DshAdapter(home)


def run(adapter, restart_cmd: str | None = None) -> int:
    path = adapter.registry_path()
    if not str(path) or not Path(path).exists():
        log(f"注册表不存在：{path}，跳过")
        write_result("guard", True, False, f"注册表不存在：{path}")
        return 0

    with file_lock(Path(path)):
        data = adapter.load()
        disk = adapter.disk_ids()
        if not disk:
            log("磁盘上没有可登记的 id，跳过")
            write_result("guard", True, False, "磁盘无 id")
            return 0

        missing = adapter.merge(data, disk)
        if not missing:
            write_result("guard", True, False, "无变更")
            return 0
        log(f"发现 {len(missing)} 个未登记：{missing}")

        # 写前重读：检查期间宿主可能已写入新清单，直接覆盖会把它冲掉。
        try:
            latest = adapter.load()
        except Exception:  # noqa: BLE001
            latest = data
        missing2 = adapter.merge(latest, disk)
        if missing2:
            log(f"写前重读又发现 {len(missing2)} 个：{missing2}")

        backup = adapter.save(latest)
        log(f"已写回（备份 {backup or '无'}）")
        write_result("guard", True, True, f"补登记 {len(missing2 or missing)} 个")

        if restart_cmd:
            r = subprocess.run(restart_cmd, shell=True, capture_output=True, text=True)
            log(f"重启命令 {'成功' if r.returncode == 0 else '失败'}：{restart_cmd}")
            if r.returncode != 0:
                log(r.stderr.strip())
                return 1
        return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="通用注册表守卫")
    p.add_argument("--adapter", default=os.environ.get("ANCHOR_ADAPTER", "dsh"),
                   choices=["dsh", "jsonfile"])
    p.add_argument("--home", default=None, help="DSH_HOME（仅 dsh 适配器）")
    p.add_argument("--restart", default=os.environ.get("RESTART_CMD"),
                   help="写回后执行的生效命令")
    args = p.parse_args(argv)
    adapter = make_adapter(args.adapter, Path(args.home) if args.home else None)
    return run(adapter, args.restart)


if __name__ == "__main__":
    raise SystemExit(main())
