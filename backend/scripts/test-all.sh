#!/usr/bin/env bash
set -euo pipefail

# 全量测试：Redis + Docker + QEMU 集成
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
BACKEND_DIR="${ROOT_DIR}/backend"

# 避免 Docker Desktop 的 gpg 凭据锁问题（可通过 TC_AGENT_KEEP_DOCKER_CONFIG=1 关闭）
if [[ -z "${DOCKER_CONFIG:-}" && "${TC_AGENT_KEEP_DOCKER_CONFIG:-}" != "1" ]]; then
  export DOCKER_CONFIG=/tmp/docker-config
  mkdir -p "$DOCKER_CONFIG"
fi

# 兼容 Docker Desktop 的 socket
if [[ -z "${DOCKER_HOST:-}" && -S "${HOME}/.docker/desktop/docker.sock" ]]; then
  export DOCKER_HOST="unix://${HOME}/.docker/desktop/docker.sock"
fi

if ! docker info >/dev/null 2>&1; then
  echo "Docker 未启动，无法执行全量测试"
  exit 1
fi

# 准备 Redis
if ! docker ps --format '{{.Names}}' | grep -q '^tc-agent-redis$'; then
  if ! docker image inspect redis:7 >/dev/null 2>&1; then
    docker pull redis:7
  fi
  docker run -d --name tc-agent-redis -p 6379:6379 redis:7 >/dev/null
fi

export TC_AGENT_REDIS_URL="${TC_AGENT_REDIS_URL:-redis://localhost:6379/0}"
export TC_AGENT_IT_RUN_QEMU=1

cd "$BACKEND_DIR"
pytest -q
