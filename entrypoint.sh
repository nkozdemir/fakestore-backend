#!/bin/sh
set -euo pipefail

APP_DIR=${DJANGO_APP_DIR:-backend}
MANAGE_CMD="python ${APP_DIR}/manage.py"
migrations_sentinel=${ENTRYPOINT_MIGRATIONS_SENTINEL:-}

if [ -n "$migrations_sentinel" ]; then
  rm -f "$migrations_sentinel"
fi

wait_for() {
  host="$1"
  port="$2"
  service="$3"
  timeout="${4:-60}"

  echo "Waiting for ${service} at ${host}:${port} (timeout: ${timeout}s)..."
  python - <<'PY' "$host" "$port" "$timeout" "$service"
import socket
import sys
import time

host = sys.argv[1]
port = int(sys.argv[2])
timeout = int(sys.argv[3])
service = sys.argv[4]

deadline = time.time() + timeout
last_error = None

while True:
    try:
        with socket.create_connection((host, port), timeout=5):
            print(f"{service} is available at {host}:{port}")
            sys.exit(0)
    except OSError as exc:
        last_error = exc
        if time.time() >= deadline:
            print(f"ERROR: Timed out waiting for {service} at {host}:{port} -> {exc}")
            sys.exit(1)
        time.sleep(1)
PY
}

postgres_host=${POSTGRES_HOST:-db}
postgres_port=${POSTGRES_PORT:-5432}

redis_host=${REDIS_HOST:-}
redis_port=${REDIS_PORT:-}

if [ -z "$redis_host" ] || [ -z "$redis_port" ]; then
  if [ -n "${REDIS_URL:-}" ]; then
    read redis_host redis_port <<EOF
$(python - <<'PY' "${REDIS_URL:-}"
from urllib.parse import urlparse
import sys

url = urlparse(sys.argv[1])
print((url.hostname or 'redis'), (url.port or 6379))
PY
)
EOF
  else
    redis_host=${redis_host:-redis}
    redis_port=${redis_port:-6379}
  fi
fi

wait_for "$postgres_host" "$postgres_port" "Postgres"
wait_for "$redis_host" "${redis_port:-6379}" "Redis"

echo "Running database migrations..."
${MANAGE_CMD} migrate --noinput

if [ -n "$migrations_sentinel" ]; then
  touch "$migrations_sentinel"
fi

echo "Launching application: $*"
exec "$@"
