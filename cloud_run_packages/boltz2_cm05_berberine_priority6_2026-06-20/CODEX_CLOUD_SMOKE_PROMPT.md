Run the CM05 berberine Boltz2 smoke test and commit the diagnostic artifacts.

Work in `cloud_run_packages/boltz2_cm05_berberine_priority6_2026-06-20`.

Required command:

```bash
bash run_cloud_smoke.sh
```

Important:
- This smoke test runs PKMYT1 only.
- Do not run the formal six-target batch in this task.
- Commit generated `cloud_results/` files, including status TSV, logs, HTML, and tar.gz.
- In the final response, report whether PKMYT1 produced CIF, confidence JSON, affinity JSON, and the main error if it failed.

Scientific boundary: Boltz2 outputs are computational prioritization results only, not experimental binding evidence.
