Run the Tahoe-100M CHK1i-sensitive-state pseudobulk projection package in this repository.

Work in `cloud_run_packages/tahoe_chk1i_codex_cloud_2026-06-18`.

Goal:
1. Run `bash run_full_tahoe_projection.sh` if the cloud environment has at least 120 GB free disk.
2. If free disk is below 120 GB, run `bash run_index_only_tahoe_projection.sh` and report that full scoring needs a larger environment.
3. Preserve all generated files in the package directory and in `results/pancancer_chk1i_sensitizer_2026-06-17/tahoe_state_induction/`.
4. Report:
   - number of scanned Tahoe pseudobulk shards
   - number of exact candidate row groups
   - number of condition scores
   - parent-drug summary
   - MoA summary
   - organ/cell-line summary
   - read failures and QC gate status

Scientific boundary:
Use language such as "CHK1i-sensitive-like transcriptional state projection". Do not state that Tahoe proves CHK1i sensitization, synergy, rescue, drug combination efficacy, or causal mechanism.

Expected main outputs:
- `tahoe_chk1i_projection_outputs.tar.gz` for full scoring, or `tahoe_chk1i_projection_index_only_outputs.tar.gz` for index-only
- `results/pancancer_chk1i_sensitizer_2026-06-17/tahoe_state_induction/tables/tahoe_condition_analysis_manifest.tsv`
- `results/pancancer_chk1i_sensitizer_2026-06-17/tahoe_state_induction/tables/tahoe_pseudobulk_chk1i_projection_scores.tsv`
- `results/pancancer_chk1i_sensitizer_2026-06-17/tahoe_state_induction/tables/tahoe_pseudobulk_parent_drug_summary.tsv`
- `results/pancancer_chk1i_sensitizer_2026-06-17/tahoe_state_induction/tables/tahoe_pseudobulk_moa_summary.tsv`
- `results/pancancer_chk1i_sensitizer_2026-06-17/tahoe_state_induction/qc/tahoe_pseudobulk_chk1i_projection_qc.json`
