#!/usr/bin/env bash
set +e
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"
mkdir -p cloud_results/logs cloud_results/status cloud_results/tables cloud_results/html
{
  echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] starting CM05 Boltz2 formal run"
  if [ -d /caas_toolbox ] && [ -w /caas_toolbox ]; then
    export BOLTZ_CACHE_DIR="${BOLTZ_CACHE_DIR:-/caas_toolbox/boltz2_cm05_cache}"
    export TMPDIR="${TMPDIR:-/caas_toolbox/tmp}"
  else
    export BOLTZ_CACHE_DIR="${BOLTZ_CACHE_DIR:-$ROOT_DIR/.boltz_cache}"
    export TMPDIR="${TMPDIR:-$ROOT_DIR/tmp}"
  fi
  mkdir -p "$BOLTZ_CACHE_DIR" "$TMPDIR"
  PYTHON_BIN="${PYTHON_BIN:-}"
  if [ -z "$PYTHON_BIN" ]; then
    if command -v python3.11 >/dev/null 2>&1; then
      PYTHON_BIN="$(command -v python3.11)"
    elif command -v pyenv >/dev/null 2>&1; then
      pyenv install -s 3.11.15
      PYTHON_BIN="$(pyenv root)/versions/3.11.15/bin/python"
    else
      PYTHON_BIN="$(command -v python3 || command -v python)"
    fi
  fi
  "$PYTHON_BIN" -m venv .venv_boltz2_cloud
  . .venv_boltz2_cloud/bin/activate
  python -m pip install --upgrade pip
  python -m pip install -r requirements.txt
  export BOLTZ_RUN_MODE=formal
  python scripts/run_boltz2_cloud.py
  echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] formal run finished"
} > cloud_results/logs/cloud_formal_entrypoint.log 2>&1
exit 0
