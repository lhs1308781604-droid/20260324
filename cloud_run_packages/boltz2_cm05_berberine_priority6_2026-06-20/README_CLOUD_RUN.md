# CM05 berberine Boltz2 Cloud Run Package

Purpose: run Boltz2 on CM05-only berberine docking priority candidates.

Scope:
- Smoke: PKMYT1 only.
- Formal: PKMYT1, TGFBR1, AURKB, TYMS, ENDOG, FLVCR1.

Inputs:
- `tables/cloud_priority6_candidate_manifest.tsv`
- `inputs/yaml_template/*.yaml`
- `inputs/yaml_no_template/*.yaml`
- `inputs/templates/*.pdb`

Run smoke:

```bash
cd cloud_run_packages/boltz2_cm05_berberine_priority6_2026-06-20
bash run_cloud_smoke.sh
```

Run formal:

```bash
cd cloud_run_packages/boltz2_cm05_berberine_priority6_2026-06-20
bash run_cloud_formal.sh
```

Output:
- `cloud_results/cloud_run_status.md`
- `cloud_results/status/boltz2_cm05_status.tsv`
- `cloud_results/tables/boltz2_cm05_summary.tsv`
- `cloud_results/html/CM05_berberine_priority6_boltz2_cloud_result.html`
- `cloud_results/boltz2_cm05_cloud_return.tar.gz`

The scripts exit 0 even when Boltz2 fails so Codex Cloud can return logs and status files. The status table records target-level success or failure.

Scientific boundary: Boltz2 outputs are computational prioritization results for follow-up selection. They are not experimental binding evidence.
