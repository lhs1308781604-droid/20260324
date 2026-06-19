#!/usr/bin/env bash
set +e
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"
mkdir -p cloud_results/logs cloud_results/status cloud_results/tables cloud_results/html
LOG=cloud_results/logs/cloud_env_debug.log
STATUS=cloud_results/cloud_env_debug_status.md
{
  echo "# CM05 Boltz2 Cloud Env Debug"
  echo "started_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "pwd=$(pwd)"
  echo "user=$(whoami)"
  echo "shell=${SHELL:-unknown}"
  echo
  echo '[disk]'
  df -h . / /caas_toolbox 2>&1
  echo
  echo '[python paths]'
  command -v python || true; python --version || true
  command -v python3 || true; python3 --version || true
  command -v python3.11 || true; python3.11 --version || true
  command -v pyenv || true; pyenv --version || true; pyenv versions || true
  echo
  echo '[try choose python]'
  PYTHON_BIN="${PYTHON_BIN:-}"
  if [ -z "$PYTHON_BIN" ]; then
    if command -v pyenv >/dev/null 2>&1 && [ -x "$(pyenv root)/versions/3.11.15/bin/python" ]; then
      PYTHON_BIN="$(pyenv root)/versions/3.11.15/bin/python"
    elif command -v python3.11 >/dev/null 2>&1 && python3.11 --version >/dev/null 2>&1; then
      PYTHON_BIN="$(command -v python3.11)"
    elif command -v pyenv >/dev/null 2>&1; then
      echo 'pyenv install -s 3.11.15 starting'
      pyenv install -s 3.11.15
      echo "pyenv install exit=$?"
      PYTHON_BIN="$(pyenv root)/versions/3.11.15/bin/python"
    else
      PYTHON_BIN="$(command -v python3 || command -v python)"
    fi
  fi
  echo "PYTHON_BIN=$PYTHON_BIN"
  "$PYTHON_BIN" --version || true
  echo
  echo '[try venv]'
  "$PYTHON_BIN" -m venv .venv_boltz2_cloud
  echo "venv_exit=$?"
  . .venv_boltz2_cloud/bin/activate
  python --version
  python -m pip --version
  python -m pip install --upgrade pip
  echo "pip_upgrade_exit=$?"
  python -m pip install -r requirements.txt
  echo "requirements_exit=$?"
  command -v boltz || true
  boltz --help | head -40 || true
  echo "finished_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
} > "$LOG" 2>&1
cp "$LOG" "$STATUS"
tar -czf cloud_results/boltz2_env_debug_return.tar.gz cloud_results/logs cloud_results/cloud_env_debug_status.md 2>/dev/null
exit 0
