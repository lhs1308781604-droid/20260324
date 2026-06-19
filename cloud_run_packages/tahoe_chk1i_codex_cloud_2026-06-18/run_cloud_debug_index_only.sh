#!/usr/bin/env bash

# Diagnostic entrypoint for Codex Cloud.
# It always writes logs/status and exits 0 so the cloud task can return a diff
# even when dependency installation, HuggingFace access, or Tahoe scanning fails.

set +e

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="$ROOT_DIR/cloud_debug_logs"
STATUS_FILE="$ROOT_DIR/cloud_run_status.md"
mkdir -p "$LOG_DIR"

RUN_STARTED_UTC="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
MAIN_LOG="$LOG_DIR/cloud_debug_main.log"
ENV_LOG="$LOG_DIR/cloud_debug_environment.log"
PIP_LOG="$LOG_DIR/pip_install.log"
RUN_LOG="$LOG_DIR/tahoe_index_only_run.log"
SUMMARY_LOG="$LOG_DIR/output_summary.log"

log() {
  printf '[%s] %s\n' "$(date -u +"%Y-%m-%dT%H:%M:%SZ")" "$*" | tee -a "$MAIN_LOG"
}

record_environment() {
  {
    echo "run_started_utc=$RUN_STARTED_UTC"
    echo "root_dir=$ROOT_DIR"
    echo "pwd=$(pwd)"
    echo "user=$(whoami 2>/dev/null)"
    echo "shell=${SHELL:-unknown}"
    echo "git_branch=$(git rev-parse --abbrev-ref HEAD 2>/dev/null)"
    echo "git_head=$(git rev-parse HEAD 2>/dev/null)"
    echo
    echo "[disk]"
    df -h 2>&1
    echo
    echo "[python]"
    command -v python 2>&1
    python --version 2>&1
    python -m pip --version 2>&1
    echo
    echo "[package files]"
    find "$ROOT_DIR" -maxdepth 3 -type f | sort
    echo
    echo "[selected env]"
    env | sort | grep -E '^(HF_HOME|TMPDIR|PIP_CACHE_DIR|PROJECT_ROOT|RESULT_ROOT|PATH|PYTHONPATH)='
  } > "$ENV_LOG" 2>&1
}

choose_scratch() {
  if [ -d "/caas_toolbox" ] && [ -w "/caas_toolbox" ]; then
    export HF_HOME="${HF_HOME:-/caas_toolbox/tahoe_hf_cache}"
    export TMPDIR="${TMPDIR:-/caas_toolbox/tmp}"
    export PIP_CACHE_DIR="${PIP_CACHE_DIR:-/caas_toolbox/pip_cache}"
  else
    export HF_HOME="${HF_HOME:-$ROOT_DIR/.hf_cache}"
    export TMPDIR="${TMPDIR:-$ROOT_DIR/tmp}"
    export PIP_CACHE_DIR="${PIP_CACHE_DIR:-$ROOT_DIR/.pip_cache}"
  fi
  mkdir -p "$HF_HOME" "$TMPDIR" "$PIP_CACHE_DIR"
}

write_status() {
  local pip_code="$1"
  local import_code="$2"
  local run_code="$3"
  local summary_code="$4"
  local tar_code="$5"
  local run_finished_utc
  run_finished_utc="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
  {
    echo "# Tahoe CHK1i Cloud Debug Status"
    echo
    echo "- run_started_utc: $RUN_STARTED_UTC"
    echo "- run_finished_utc: $run_finished_utc"
    echo "- package_dir: $ROOT_DIR"
    echo "- git_branch: $(git rev-parse --abbrev-ref HEAD 2>/dev/null)"
    echo "- git_head: $(git rev-parse HEAD 2>/dev/null)"
    echo "- HF_HOME: ${HF_HOME:-unset}"
    echo "- TMPDIR: ${TMPDIR:-unset}"
    echo "- PROJECT_ROOT: ${PROJECT_ROOT:-unset}"
    echo "- RESULT_ROOT: ${RESULT_ROOT:-unset}"
    echo "- pip_install_exit_code: $pip_code"
    echo "- python_import_exit_code: $import_code"
    echo "- tahoe_index_only_exit_code: $run_code"
    echo "- output_summary_exit_code: $summary_code"
    echo "- artifact_tar_exit_code: $tar_code"
    echo
    echo "## Output Checks"
    for file in \
      "$RESULT_ROOT/tahoe_state_induction/qc/tahoe_pseudobulk_chk1i_projection_qc.json" \
      "$RESULT_ROOT/tahoe_state_induction/tables/tahoe_pseudobulk_candidate_rowgroup_index.tsv" \
      "$RESULT_ROOT/tahoe_state_induction/tables/tahoe_condition_analysis_manifest.tsv" \
      "$ROOT_DIR/tahoe_chk1i_cloud_debug_outputs.tar.gz"; do
      if [ -f "$file" ]; then
        bytes="$(wc -c < "$file" 2>/dev/null)"
        echo "- present: $file (${bytes} bytes)"
      else
        echo "- missing: $file"
      fi
    done
    echo
    echo "## Scientific Boundary"
    echo "This diagnostic run only tests Tahoe-100M CHK1i-sensitive-like state projection plumbing. It is not CHK1i synergy, rescue, or causal sensitization proof."
  } > "$STATUS_FILE"
}

summarize_outputs() {
  python - <<'PY'
import json
import os
from pathlib import Path

import pandas as pd

result_root = Path(os.environ["RESULT_ROOT"])
qc = result_root / "tahoe_state_induction/qc/tahoe_pseudobulk_chk1i_projection_qc.json"
index = result_root / "tahoe_state_induction/tables/tahoe_pseudobulk_candidate_rowgroup_index.tsv"
condition = result_root / "tahoe_state_induction/tables/tahoe_condition_analysis_manifest.tsv"

print("result_root", result_root)
if qc.exists():
    data = json.loads(qc.read_text())
    keys = [
        "index_only",
        "max_files",
        "n_scanned_files",
        "n_row_groups_matched",
        "n_ambiguous_range_row_groups",
        "n_files_with_matched_row_groups",
        "n_condition_scores",
        "n_read_failures",
    ]
    for key in keys:
        print(f"{key}\t{data.get(key)}")
else:
    print("missing_qc", qc)

for path in [index, condition]:
    if path.exists():
        df = pd.read_csv(path, sep="\t")
        print(f"{path.name}\trows={len(df)}\tcols={len(df.columns)}")
        if "scan_status" in df.columns:
            print("scan_status_counts", df["scan_status"].value_counts(dropna=False).to_dict())
        if "row_group_matched" in df.columns:
            print("matched_rows", int(df["row_group_matched"].fillna(False).sum()))
        if "row_group_ambiguous_target_range" in df.columns:
            print("ambiguous_rows", int(df["row_group_ambiguous_target_range"].fillna(False).sum()))
    else:
        print("missing_table", path)
PY
}

choose_scratch
export PROJECT_ROOT="${PROJECT_ROOT:-$ROOT_DIR}"
export RESULT_ROOT="${RESULT_ROOT:-$PROJECT_ROOT/results/pancancer_chk1i_sensitizer_2026-06-17}"
export TAHOE_MAX_FILES="${TAHOE_MAX_FILES:-2}"
export FOOTER_WORKERS="${FOOTER_WORKERS:-2}"

log "Starting cloud diagnostic index-only run."
record_environment

log "Installing Python requirements."
python -m pip install --upgrade pip > "$PIP_LOG" 2>&1
python -m pip install --cache-dir "$PIP_CACHE_DIR" -r "$ROOT_DIR/requirements.txt" >> "$PIP_LOG" 2>&1
PIP_CODE=$?
log "pip install exit code: $PIP_CODE"

python - <<'PY' >> "$PIP_LOG" 2>&1
import huggingface_hub
import numpy
import pandas
import pyarrow
print("imports_ok", pandas.__version__, numpy.__version__, pyarrow.__version__, huggingface_hub.__version__)
PY
IMPORT_CODE=$?
log "python import exit code: $IMPORT_CODE"

RUN_CODE=127
if [ "$PIP_CODE" -eq 0 ] && [ "$IMPORT_CODE" -eq 0 ]; then
  log "Running Tahoe index-only diagnostic with max files: $TAHOE_MAX_FILES."
  python "$RESULT_ROOT/tahoe_state_induction/scripts/run_tahoe_pseudobulk_chk1i_projection.py" \
    --max-files "$TAHOE_MAX_FILES" \
    --footer-workers "$FOOTER_WORKERS" \
    --read-workers 1 \
    --index-only > "$RUN_LOG" 2>&1
  RUN_CODE=$?
  log "Tahoe index-only exit code: $RUN_CODE"
else
  log "Skipping Tahoe run because dependency setup failed."
fi

summarize_outputs > "$SUMMARY_LOG" 2>&1
SUMMARY_CODE=$?
log "Output summary exit code: $SUMMARY_CODE"

write_status "$PIP_CODE" "$IMPORT_CODE" "$RUN_CODE" "$SUMMARY_CODE" "pending"

tar -czf "$ROOT_DIR/tahoe_chk1i_cloud_debug_outputs.tar.gz" \
  -C "$ROOT_DIR" cloud_debug_logs cloud_run_status.md \
  -C "$RESULT_ROOT" tahoe_state_induction/tables tahoe_state_induction/qc tahoe_state_induction/logs \
  >> "$MAIN_LOG" 2>&1
TAR_CODE=$?
log "Artifact tar exit code: $TAR_CODE"

write_status "$PIP_CODE" "$IMPORT_CODE" "$RUN_CODE" "$SUMMARY_CODE" "$TAR_CODE"
log "Finished cloud diagnostic. Status file: $STATUS_FILE"

exit 0
