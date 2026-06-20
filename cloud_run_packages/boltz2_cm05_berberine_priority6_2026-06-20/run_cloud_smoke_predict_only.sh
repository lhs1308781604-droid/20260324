#!/usr/bin/env bash
set +e
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"
mkdir -p cloud_results/logs cloud_results/status cloud_results/tables cloud_results/html

{
  echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] starting CM05 Boltz2 smoke prediction only"
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
  mkdir -p "$BOLTZ_CACHE_DIR" "$TMPDIR"
  echo "PERSISTENT_VENV: $PERSISTENT_VENV"
  echo "BOLTZ_CACHE_DIR: $BOLTZ_CACHE_DIR"
  echo "TMPDIR: $TMPDIR"

  if [ ! -x "$PERSISTENT_VENV/bin/python" ]; then
    echo -e "stage\tstatus\tpersistent_venv\nsmoke_predict\tmissing_persistent_env\t$PERSISTENT_VENV" > cloud_results/status/smoke_predict_only_status.tsv
    echo "persistent environment missing; run run_cloud_prepare_persistent_env.sh first"
    exit 0
  fi

  . "$PERSISTENT_VENV/bin/activate"
  python --version
  python - <<'PY'
import importlib.util
mods = ["boltz", "torch", "rdkit", "pandas", "Bio"]
print({m: bool(importlib.util.find_spec(m)) for m in mods})
PY
  boltz --help | head -30 || true
  command -v nvidia-smi >/dev/null 2>&1 && nvidia-smi || true

  export BOLTZ_RUN_MODE=smoke
  export BOLTZ_RECYCLING_STEPS="${BOLTZ_RECYCLING_STEPS:-1}"
  export BOLTZ_SAMPLING_STEPS="${BOLTZ_SAMPLING_STEPS:-25}"
  export BOLTZ_SAMPLING_STEPS_AFFINITY="${BOLTZ_SAMPLING_STEPS_AFFINITY:-25}"
  export BOLTZ_DIFFUSION_SAMPLES="${BOLTZ_DIFFUSION_SAMPLES:-1}"
  export BOLTZ_DIFFUSION_SAMPLES_AFFINITY="${BOLTZ_DIFFUSION_SAMPLES_AFFINITY:-1}"
  boltz_timeout="${BOLTZ_SMOKE_TIMEOUT_SECONDS:-420}"
  echo "boltz_smoke_timeout_seconds: $boltz_timeout"
  timeout "$boltz_timeout" python scripts/run_boltz2_cloud.py
  boltz_status=$?
  echo "boltz_smoke_status: $boltz_status"
  echo -e "stage\tstatus\texit_code\tpersistent_venv\nsmoke_predict\tcompleted_or_timeout\t$boltz_status\t$PERSISTENT_VENV" > cloud_results/status/smoke_predict_only_status.tsv
  echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] smoke prediction only finished"
} > cloud_results/logs/smoke_predict_only_entrypoint.log 2>&1

exit 0
