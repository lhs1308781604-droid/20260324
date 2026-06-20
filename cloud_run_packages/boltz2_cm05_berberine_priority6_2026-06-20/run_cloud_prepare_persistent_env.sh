#!/usr/bin/env bash
set +e
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"
mkdir -p cloud_results/logs cloud_results/status

{
  echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] preparing persistent CM05 Boltz2 environment"
  echo "pwd: $(pwd)"
  echo "git_commit: $(git rev-parse HEAD 2>/dev/null)"

  if [ -d /caas_toolbox ] && [ -w /caas_toolbox ]; then
    export PERSISTENT_VENV="${PERSISTENT_VENV:-/caas_toolbox/boltz2_cm05_venv_py311}"
    export BOLTZ_CACHE_DIR="${BOLTZ_CACHE_DIR:-/caas_toolbox/boltz2_cm05_cache}"
    export TMPDIR="${TMPDIR:-/caas_toolbox/tmp}"
  else
    export PERSISTENT_VENV="${PERSISTENT_VENV:-$ROOT_DIR/.venv_boltz2_cloud_persistent}"
    export BOLTZ_CACHE_DIR="${BOLTZ_CACHE_DIR:-$ROOT_DIR/.boltz_cache}"
    export TMPDIR="${TMPDIR:-$ROOT_DIR/tmp}"
  fi
  mkdir -p "$(dirname "$PERSISTENT_VENV")" "$BOLTZ_CACHE_DIR" "$TMPDIR"
  echo "PERSISTENT_VENV: $PERSISTENT_VENV"
  echo "BOLTZ_CACHE_DIR: $BOLTZ_CACHE_DIR"
  echo "TMPDIR: $TMPDIR"

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
  echo "PYTHON_BIN: $PYTHON_BIN"
  "$PYTHON_BIN" --version

  if [ ! -x "$PERSISTENT_VENV/bin/python" ]; then
    "$PYTHON_BIN" -m venv "$PERSISTENT_VENV"
    echo "created_persistent_venv: yes"
  else
    echo "created_persistent_venv: no"
  fi

  . "$PERSISTENT_VENV/bin/activate"
  python --version
  python -m pip --version
  python -m pip install --upgrade pip

  install_timeout="${PIP_INSTALL_TIMEOUT_SECONDS:-480}"
  echo "pip_install_timeout_seconds: $install_timeout"
  timeout "$install_timeout" python -m pip install -r requirements.txt
  pip_install_status=$?
  echo "pip_install_status: $pip_install_status"

  python - <<'PY'
import importlib.util
import json
import sys

mods = ["boltz", "torch", "rdkit", "pandas", "Bio"]
print(json.dumps({
    "python": sys.executable,
    "version": sys.version,
    "modules": {m: bool(importlib.util.find_spec(m)) for m in mods},
}, ensure_ascii=False, indent=2))
PY
  import_probe_status=$?
  echo "import_probe_status: $import_probe_status"

  if [ "$pip_install_status" -eq 0 ] && [ "$import_probe_status" -eq 0 ]; then
    echo -e "stage\tstatus\tpersistent_venv\npersistent_env\tpassed\t$PERSISTENT_VENV" > cloud_results/status/persistent_env_status.tsv
  else
    echo -e "stage\tstatus\tpersistent_venv\tpip_install_status\timport_probe_status\npersistent_env\tfailed_or_timeout\t$PERSISTENT_VENV\t$pip_install_status\t$import_probe_status" > cloud_results/status/persistent_env_status.tsv
  fi

  echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] persistent environment preparation finished"
} > cloud_results/logs/persistent_env_entrypoint.log 2>&1

exit 0
