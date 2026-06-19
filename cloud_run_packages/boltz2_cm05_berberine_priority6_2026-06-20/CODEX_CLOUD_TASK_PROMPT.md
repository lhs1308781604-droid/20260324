Run the CM05 berberine Boltz2 formal six-target batch and commit the result artifacts.

Work in `cloud_run_packages/boltz2_cm05_berberine_priority6_2026-06-20`.

Required command:

```bash
bash run_cloud_formal.sh
```

Important:
- Run the six candidates serially in manifest order.
- For each candidate, use template YAML first; if template fails, use the no-template fallback for that candidate only.
- Do not stop the whole batch because one target fails.
- Commit generated `cloud_results/` files, including status TSV, logs, HTML, and tar.gz.
- Do not commit Boltz2 cache directories or virtual environments.
- In the final response, report completed target count, failed targets and reasons, affinity_pred_value, affinity_probability_binary, and which candidates should move to pose review.

Scientific boundary: Boltz2 outputs are computational prioritization results only, not experimental binding evidence.
