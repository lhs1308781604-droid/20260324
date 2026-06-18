# Tahoe CHK1i-sensitive-state Cloud Run Package

Purpose: run the full Tahoe-100M `pseudobulk_differential_expression` projection against the pan-cancer CHK1i-sensitive minus resistant ruler.

Inputs included:
- CHK1i consensus ruler: `results/pancancer_chk1i_sensitizer_2026-06-17/tables/step3_chk1i_sensitive_resistant_consensus_ruler.tsv`
- Tahoe candidate coverage: `results/pancancer_chk1i_sensitizer_2026-06-17/tables/step5_tahoe_candidate_drug_coverage.tsv`
- Query up/down genes: `results/pancancer_chk1i_sensitizer_2026-06-17/query_packages/`
- Tahoe metadata parquet files: `results/pancancer_chk1i_sensitizer_2026-06-17/raw_probe/tahoe_hf/metadata/`
- Execution script: `results/pancancer_chk1i_sensitizer_2026-06-17/tahoe_state_induction/scripts/run_tahoe_pseudobulk_chk1i_projection.py`

Full run:

```bash
cd cloud_run_packages/tahoe_chk1i_codex_cloud_2026-06-18
bash run_full_tahoe_projection.sh
```

Index-only run:

```bash
cd cloud_run_packages/tahoe_chk1i_codex_cloud_2026-06-18
bash run_index_only_tahoe_projection.sh
```

Resource expectation:
- Full scoring can download many Tahoe pseudobulk parquet shards through HuggingFace cache.
- Use a cloud machine with at least 120 GB free disk; 200 GB is safer.
- If disk is limited, run index-only first and then split scoring by shard groups.

Claim boundary:
- Positive projection means a drug-treated pseudobulk profile moves toward a CHK1i-sensitive-like transcriptional state.
- This does not prove CHK1i synergy, rescue, combination efficacy, or causal mechanism.
