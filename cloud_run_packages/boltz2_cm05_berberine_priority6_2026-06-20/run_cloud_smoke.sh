#!/usr/bin/env bash
set +e
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"
mkdir -p cloud_results/logs cloud_results/status cloud_results/tables cloud_results/html
{
  echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] starting CM05 Boltz2 smoke run"
  if [ -d /caas_toolbox ] && [ -w /caas_toolbox ]; then
    export BOLTZ_CACHE_DIR="${BOLTZ_CACHE_DIR:-/caas_toolbox/boltz2_cm05_cache}"
    export TMPDIR="${TMPDIR:-/caas_toolbox/tmp}"
  else
    export BOLTZ_CACHE_DIR="${BOLTZ_CACHE_DIR:-$ROOT_DIR/.boltz_cache}"
    export TMPDIR="${TMPDIR:-$ROOT_DIR/tmp}"
  fi
  mkdir -p "$BOLTZ_CACHE_DIR" "$TMPDIR"
  python -m pip install --upgrade pip
  python -m pip install -r requirements.txt
  export BOLTZ_RUN_MODE=smoke
  python scripts/run_boltz2_cloud.py
  echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] smoke run finished"
} > cloud_results/logs/cloud_smoke_entrypoint.log 2>&1
exit 0
