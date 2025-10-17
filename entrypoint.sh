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

generate_schema="${GENERATE_OPENAPI_ON_START:-1}"
schema_dir="${APP_DIR}/static/schema"
schema_json="${schema_dir}/openapi.json"
schema_yaml="${schema_dir}/openapi.yaml"

if [ "$generate_schema" != "0" ]; then
  need_schema=0
  if [ ! -f "$schema_json" ] || [ ! -s "$schema_json" ]; then
    need_schema=1
  elif [ ! -f "$schema_yaml" ] || [ ! -s "$schema_yaml" ]; then
    need_schema=1
  fi

  if [ "$need_schema" -eq 1 ]; then
    echo "Exporting OpenAPI schema artifacts to ${schema_dir}..."
    mkdir -p "$schema_dir"
    tmp_json="$(mktemp /tmp/openapi.XXXXXX.json)"
    cleanup_tmp() {
      rm -f "$tmp_json"
    }
    trap cleanup_tmp EXIT
    if ${MANAGE_CMD} spectacular --file "$tmp_json" --format openapi-json; then
      python - "$tmp_json" "$schema_json" "$schema_yaml" <<'PY'
import json
import sys
from pathlib import Path

tmp_json, dest_json, dest_yaml = sys.argv[1:4]
data = json.load(open(tmp_json))
Path(dest_json).write_text(json.dumps(data, indent=2))
print(f"Wrote JSON schema to {dest_json}")
try:
    import yaml  # type: ignore
except ModuleNotFoundError:
    print("PyYAML not installed; skipping YAML schema export.")
else:
    Path(dest_yaml).write_text(yaml.safe_dump(data, sort_keys=False))
    print(f"Wrote YAML schema to {dest_yaml}")
PY
    else
      echo "WARNING: Failed to generate OpenAPI schema; continuing start-up." >&2
    fi
    trap - EXIT
    cleanup_tmp
  fi
fi

echo "Launching application: $*"
exec "$@"
