#!/usr/bin/env bash
# 生成三个独立分发包（不依赖仓库其余目录）：
#   dist/anchor-quickstart-<ver>.tar.gz   简单安装：install.sh + payload
#   dist/anchor-deploy-<ver>.tar.gz       完整部署：systemd + scripts + payload
#   dist/anchor-src-<ver>.tar.gz          完整源码（git archive）
#
# 用法：./scripts/build-release.sh [版本号]
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VER="${1:-0.1.0}"
DIST="$ROOT/dist"
STAGE="$(mktemp -d /tmp/anchor-release-XXXX)"
trap 'rm -rf "$STAGE"' EXIT

rm -rf "$DIST"
mkdir -p "$DIST"

echo "== quickstart"
Q="$STAGE/anchor-quickstart-$VER"
mkdir -p "$Q/payload/adapters"
cp "$ROOT/quickstart/install.sh" "$ROOT/quickstart/README.md" "$Q/"
for f in memory.py activation.py workspace_guard.py anchor.py registry_guard.py; do
  cp "$ROOT/src/$f" "$Q/payload/"
done
cp -r "$ROOT/src/adapters/." "$Q/payload/adapters/"
find "$Q/payload" -name __pycache__ -type d -prune -exec rm -rf {} +
cp "$ROOT/src/memory_digest.mjs" "$Q/payload/"
chmod 755 "$Q/install.sh" "$Q"/payload/*.py
chmod 644 "$Q"/payload/adapters/*.py
tar czf "$DIST/anchor-quickstart-$VER.tar.gz" -C "$STAGE" "anchor-quickstart-$VER"

echo "== deploy"
D="$STAGE/anchor-deploy-$VER"
mkdir -p "$D/payload/adapters" "$D/systemd" "$D/scripts" "$D/configs"
cp -r "$ROOT/deploy/systemd/." "$D/systemd/"
cp -r "$ROOT/deploy/scripts/." "$D/scripts/"
cp -r "$ROOT/deploy/configs/." "$D/configs/"
cp "$ROOT/deploy/README.md" "$D/"
for f in registry_guard.py workspace_guard.py anchor.py; do
  cp "$ROOT/src/$f" "$D/payload/"
done
cp -r "$ROOT/src/adapters/." "$D/payload/adapters/"
find "$D/payload" -name __pycache__ -type d -prune -exec rm -rf {} +
cp "$ROOT/src/memory_digest.mjs" "$D/payload/"
chmod 755 "$D/payload"/*.py "$D/scripts"/*.sh
chmod 644 "$D"/payload/adapters/*.py
tar czf "$DIST/anchor-deploy-$VER.tar.gz" -C "$STAGE" "anchor-deploy-$VER"

echo "== src"
git -C "$ROOT" archive --format=tar.gz --prefix="anchor-src-$VER/" HEAD -o "$DIST/anchor-src-$VER.tar.gz"

echo
echo "产出："
ls -lh "$DIST" | tail -n +2
