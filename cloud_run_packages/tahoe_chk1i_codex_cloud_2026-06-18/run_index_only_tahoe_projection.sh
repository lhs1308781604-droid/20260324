#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export PROJECT_ROOT="${PROJECT_ROOT:-$ROOT_DIR}"
export RESULT_ROOT="${RESULT_ROOT:-$PROJECT_ROOT/results/pancancer_chk1i_sensitizer_2026-06-17}"
export HF_HOME="${HF_HOME:-$PROJECT_ROOT/.hf_cache}"

FOOTER_WORKERS="${FOOTER_WORKERS:-16}"

python -m pip install --upgrade pip
python -m pip install -r "$ROOT_DIR/requirements.txt"

python "$RESULT_ROOT/tahoe_state_induction/scripts/run_tahoe_pseudobulk_chk1i_projection.py" \
  --footer-workers "$FOOTER_WORKERS" \
  --read-workers 1 \
  --index-only

tar -czf "$ROOT_DIR/tahoe_chk1i_projection_index_only_outputs.tar.gz" \
  -C "$RESULT_ROOT" \
  tahoe_state_induction/tables \
  tahoe_state_induction/qc \
  tahoe_state_induction/logs

echo "DONE: $ROOT_DIR/tahoe_chk1i_projection_index_only_outputs.tar.gz"
