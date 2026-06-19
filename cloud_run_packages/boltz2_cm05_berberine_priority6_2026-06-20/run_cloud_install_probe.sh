#!/usr/bin/env bash
set +e
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"
mkdir -p cloud_results/logs cloud_results/status

{
  echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] starting CM05 Boltz2 dependency install probe"
  echo "pwd: $(pwd)"
  echo "git_commit: $(git rev-parse HEAD 2>/dev/null)"

  if [ -d /caas_toolbox ] && [ -w /caas_toolbox ]; then
    export BOLTZ_CACHE_DIR="${BOLTZ_CACHE_DIR:-/caas_toolbox/boltz2_cm05_cache}"
    export TMPDIR="${TMPDIR:-/caas_toolbox/tmp}"
  else
    export BOLTZ_CACHE_DIR="${BOLTZ_CACHE_DIR:-$ROOT_DIR/.boltz_cache}"
    export TMPDIR="${TMPDIR:-$ROOT_DIR/tmp}"
  fi
  mkdir -p "$BOLTZ_CACHE_DIR" "$TMPDIR"
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

  "$PYTHON_BIN" -m venv .venv_boltz2_cloud
  venv_status=$?
  echo "venv_status: $venv_status"
  . .venv_boltz2_cloud/bin/activate
  python --version
  python -m pip --version

  python -m pip install --upgrade pip
  pip_upgrade_status=$?
  echo "pip_upgrade_status: $pip_upgrade_status"

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
    echo -e "probe\tstatus\ninstall_probe\tpassed" > cloud_results/status/install_probe_status.tsv
  else
    echo -e "probe\tstatus\tpip_install_status\timport_probe_status\ninstall_probe\tfailed_or_timeout\t$pip_install_status\t$import_probe_status" > cloud_results/status/install_probe_status.tsv
  fi

  echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] install probe finished"
} > cloud_results/logs/install_probe_entrypoint.log 2>&1

exit 0
