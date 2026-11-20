#!/usr/bin/env python3
"""兼容入口：DSH 注册表守卫 = 通用 registry_guard + dsh 适配器。

保留这个文件名和用法（``python3 workspace_guard.py``）是为了兼容已有的
systemd 单元和部署脚本。新用法请直接调 ``registry_guard.py``。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from registry_guard import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main(["--adapter", "dsh"]))
