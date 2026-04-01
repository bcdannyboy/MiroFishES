#!/bin/sh
set -eu

CONTAINER_NAME="${GRAPHITI_LIVE_NEO4J_CONTAINER:-mirofish-graphiti-live}"
IMAGE_NAME="${GRAPHITI_LIVE_NEO4J_IMAGE:-neo4j:5}"
HTTP_PORT="${GRAPHITI_LIVE_NEO4J_HTTP_PORT:-17474}"
BOLT_PORT="${GRAPHITI_LIVE_NEO4J_BOLT_PORT:-17687}"
NEO4J_USER="${GRAPHITI_LIVE_NEO4J_USER:-neo4j}"
NEO4J_PASSWORD="${GRAPHITI_LIVE_NEO4J_PASSWORD:-mirofish-graphiti-live}"

if ! command -v docker >/dev/null 2>&1; then
  echo "docker is required for the graphiti live verification ladder" >&2
  exit 1
fi

RUNNING_NAME="$(docker ps --filter "name=^/${CONTAINER_NAME}$" --filter status=running --format '{{.Names}}')"
if [ "${RUNNING_NAME}" != "${CONTAINER_NAME}" ]; then
  EXISTING_NAME="$(docker ps -a --filter "name=^/${CONTAINER_NAME}$" --format '{{.Names}}')"
  if [ "${EXISTING_NAME}" = "${CONTAINER_NAME}" ]; then
    docker rm -f "${CONTAINER_NAME}" >/dev/null
  fi
  docker run -d --rm \
    --name "${CONTAINER_NAME}" \
    -p "${HTTP_PORT}:7474" \
    -p "${BOLT_PORT}:7687" \
    -e "NEO4J_AUTH=${NEO4J_USER}/${NEO4J_PASSWORD}" \
    "${IMAGE_NAME}" >/dev/null
fi

attempt=0
while [ "${attempt}" -lt 60 ]; do
  if curl -fsS "http://127.0.0.1:${HTTP_PORT}" >/dev/null 2>&1; then
    if curl -fsS \
      -u "${NEO4J_USER}:${NEO4J_PASSWORD}" \
      -X POST \
      "http://127.0.0.1:${HTTP_PORT}/db/neo4j/tx/commit" \
      -H "Content-Type: application/json" \
      -d '{"statements":[{"statement":"RETURN 1 AS ok"}]}' >/dev/null 2>&1; then
      exit 0
    fi
  fi
  attempt=$((attempt + 1))
  sleep 1
done

echo "timed out waiting for ${CONTAINER_NAME} on localhost:${HTTP_PORT}/${BOLT_PORT}" >&2
exit 1
