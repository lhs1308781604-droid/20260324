#!/usr/bin/env bash
set +e
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"
mkdir -p cloud_results/logs cloud_results/status cloud_results/tables cloud_results/html

{
  echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] starting CM05 Boltz2 fast smoke"
  echo "pwd: $(pwd)"
  echo "git_commit: $(git rev-parse HEAD 2>/dev/null)"

  export BOLTZ_CACHE_DIR="${BOLTZ_CACHE_DIR:-$ROOT_DIR/.boltz_cache}"
  export TMPDIR="${TMPDIR:-$ROOT_DIR/tmp}"
  mkdir -p "$BOLTZ_CACHE_DIR" "$TMPDIR"
  echo "BOLTZ_CACHE_DIR: $BOLTZ_CACHE_DIR"
  echo "TMPDIR: $TMPDIR"

  PYTHON_BIN="${PYTHON_BIN:-}"
  if [ -z "$PYTHON_BIN" ]; then
    if command -v pyenv >/dev/null 2>&1 && [ -x "$(pyenv root)/versions/3.11.15/bin/python" ]; then
      PYTHON_BIN="$(pyenv root)/versions/3.11.15/bin/python"
    elif command -v python3.11 >/dev/null 2>&1 && python3.11 --version >/dev/null 2>&1; then
      PYTHON_BIN="$(command -v python3.11)"
    else
      PYTHON_BIN="$(command -v python3 || command -v python)"
    fi
  fi
  echo "PYTHON_BIN: $PYTHON_BIN"
  "$PYTHON_BIN" --version

  "$PYTHON_BIN" -m venv .venv_boltz2_fast_smoke
  . .venv_boltz2_fast_smoke/bin/activate
  python --version
  python -m pip install --upgrade pip

  install_timeout="${PIP_INSTALL_TIMEOUT_SECONDS:-600}"
  echo "pip_install_timeout_seconds: $install_timeout"
  timeout "$install_timeout" python -m pip install -r requirements.txt
  pip_install_status=$?
  echo "pip_install_status: $pip_install_status"
  if [ "$pip_install_status" -ne 0 ]; then
    echo -e "stage\tstatus\texit_code\npip_install\tfailed_or_timeout\t$pip_install_status" > cloud_results/status/fast_smoke_entrypoint_status.tsv
    exit 0
  fi

  export BOLTZ_RUN_MODE=smoke
  export BOLTZ_USE_MSA_SERVER=0
  export BOLTZ_USE_POTENTIALS=0
  export BOLTZ_ALLOW_FALLBACK=0
  export BOLTZ_RECYCLING_STEPS=1
  export BOLTZ_SAMPLING_STEPS=5
  export BOLTZ_SAMPLING_STEPS_AFFINITY=5
  export BOLTZ_DIFFUSION_SAMPLES=1
  export BOLTZ_DIFFUSION_SAMPLES_AFFINITY=1
  export BOLTZ_SEED=20260620

  echo "fast_smoke_params: no_msa no_potentials no_fallback recycling=1 sampling=5 affinity_sampling=5"
  boltz_timeout="${BOLTZ_FAST_SMOKE_TIMEOUT_SECONDS:-360}"
  echo "boltz_fast_smoke_timeout_seconds: $boltz_timeout"
  timeout "$boltz_timeout" python scripts/run_boltz2_cloud.py
  boltz_status=$?
  echo "boltz_fast_smoke_status: $boltz_status"
  echo -e "stage\tstatus\texit_code\nfast_smoke\tcompleted_or_timeout\t$boltz_status" > cloud_results/status/fast_smoke_entrypoint_status.tsv
  echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] fast smoke finished"
} > cloud_results/logs/fast_smoke_entrypoint.log 2>&1

exit 0
