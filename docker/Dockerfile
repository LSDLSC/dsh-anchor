# Anchor 全功能镜像：Python（记忆/激活/情绪/守卫）+ Node（会话沉淀）
FROM python:3.12-slim

RUN apt-get update \
 && apt-get install -y --no-install-recommends nodejs git ca-certificates \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /opt/anchor
COPY src/ ./src/
COPY quickstart/ ./quickstart/
COPY deploy/ ./deploy/
COPY docs/ ./docs/
COPY README.md LICENSE ./

ENV DSH_HOME=/data/dsh \
    MEMORY_DIR=/data/memory \
    PATH="/root/.local/bin:$PATH"

VOLUME ["/data/dsh", "/data/memory"]

ENTRYPOINT ["python3", "src/anchor.py"]
CMD ["status"]
