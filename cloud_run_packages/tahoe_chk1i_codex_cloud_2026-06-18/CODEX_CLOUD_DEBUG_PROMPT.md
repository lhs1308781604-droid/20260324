Run the diagnostic Tahoe-100M CHK1i-sensitive-state index-only package and commit the diagnostic artifacts.

Work in `cloud_run_packages/tahoe_chk1i_codex_cloud_2026-06-18`.

Required command:

```bash
bash run_cloud_debug_index_only.sh
```

Important:
- Do not run the full Tahoe scoring in this diagnostic task.
- The script is designed to exit 0 even if dependency installation or Tahoe access fails, so the task should still commit logs.
- Commit the generated `cloud_debug_logs/`, `cloud_run_status.md`, and `tahoe_chk1i_cloud_debug_outputs.tar.gz`.
- In the final response, summarize:
  - whether dependency installation succeeded
  - whether Python imports succeeded
  - whether Tahoe index-only execution succeeded
  - scanned shards, exact matched row groups, ambiguous row groups, condition scores, and failures if available
  - any disk, HuggingFace, runtime, or dependency limitation visible in the logs

Scientific boundary:
Use "CHK1i-sensitive-like transcriptional state projection". Do not state that Tahoe proves CHK1i sensitization, synergy, rescue, drug combination efficacy, or causal mechanism.
