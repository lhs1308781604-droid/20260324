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
  PYTHON_BIN="${PYTHON_BIN:-}"
  if [ -z "$PYTHON_BIN" ]; then
    if command -v pyenv >/dev/null 2>&1 && [ -x "$(pyenv root)/versions/3.11.15/bin/python" ]; then
      PYTHON_BIN="$(pyenv root)/versions/3.11.15/bin/python"
    elif command -v python3.11 >/dev/null 2>&1 && python3.11 --version >/dev/null 2>&1; then
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
  install_timeout="${PIP_INSTALL_TIMEOUT_SECONDS:-300}"
  echo "pip_install_timeout_seconds: $install_timeout"
  timeout "$install_timeout" python -m pip install -r requirements.txt
  pip_install_status=$?
  echo "pip_install_status: $pip_install_status"
  if [ "$pip_install_status" -ne 0 ]; then
    echo -e "stage\tstatus\texit_code\npip_install\tfailed_or_timeout\t$pip_install_status" > cloud_results/status/smoke_entrypoint_status.tsv
    echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] smoke run stopped before Boltz2 prediction"
    exit 0
  fi
  export BOLTZ_RUN_MODE=smoke
  boltz_timeout="${BOLTZ_SMOKE_TIMEOUT_SECONDS:-420}"
  echo "boltz_smoke_timeout_seconds: $boltz_timeout"
  timeout "$boltz_timeout" python scripts/run_boltz2_cloud.py
  boltz_status=$?
  echo "boltz_smoke_status: $boltz_status"
  echo -e "stage\tstatus\texit_code\nboltz_smoke\tcompleted_or_timeout\t$boltz_status" > cloud_results/status/smoke_entrypoint_status.tsv
  echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] smoke run finished"
} > cloud_results/logs/cloud_smoke_entrypoint.log 2>&1
exit 0
