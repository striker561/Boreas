#!/usr/bin/env bash

set -euo pipefail

if [[ -f .env ]]; then
	set -a
	# shellcheck disable=SC1091
	source .env
	set +a
fi

export OMP_NUM_THREADS="${REMBG_OMP_NUM_THREADS:-2}"
export OMP_WAIT_POLICY="${OMP_WAIT_POLICY:-PASSIVE}"
export MALLOC_ARENA_MAX="${MALLOC_ARENA_MAX:-2}"
export U2NET_HOME="${U2NET_HOME:-${HOME}/.u2net}"
mkdir -p "$U2NET_HOME"

if [[ -n "${VIRTUAL_ENV:-}" ]]; then
	arq_bin="${VIRTUAL_ENV}/bin/arq"
	uvicorn_bin="${VIRTUAL_ENV}/bin/uvicorn"
elif [[ -x ".venv/bin/arq" && -x ".venv/bin/uvicorn" ]]; then
	arq_bin=".venv/bin/arq"
	uvicorn_bin=".venv/bin/uvicorn"
else
	arq_bin="arq"
	uvicorn_bin="uvicorn"
fi

cleanup() {
	kill "$watchdog_pid" 2>/dev/null || true
	wait || true
}

trap cleanup EXIT INT TERM

# Start the watchdog (spawns and supervises arq workers)
python -m app.core.watchdog "$arq_bin" &
watchdog_pid=$!

# Keep uvicorn in the foreground so worker exits do not immediately terminate
# container liveness; workers are cleaned up when the API process exits.
"$uvicorn_bin" app.main:app --host 0.0.0.0 --port "${PORT:-8000}" --no-access-log