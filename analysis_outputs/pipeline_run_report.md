# Pipeline Run Report

## Phase 1 (official route + environment) status
- Completed environment/tooling checks.
- Installed `arc-state` CLI and dependencies locally.
- Verified CLI entry points (`emb`, `tx`, `tx infer`).
- Pulled official `ArcInstitute/state` repository for route verification.
- Downloaded official ST inference Colab notebook (`st_infer_colab.ipynb`) and extracted official checkpoint repo IDs.

## Phase 2 (input diagnosis) status
- Input can be parsed after a minimal compatibility cleanup copy (`AML_D0_for_State_beginner_clean.h5ad`).
- `shape`: 11641 cells × 27899 genes.
- `obs/var/X`: present.
- Species: human.
- Gene IDs: gene symbol-like (not Ensembl).
- `layers`: has `counts`; `obsm`: has `X_hvg`; `raw`: absent.
- Matrix appears log-normalized in `X` with raw-like counts in `layers['counts']`.
- Overall: structurally compatible with Arc State inference conventions (`X_hvg` present, perturbation/control metadata present).

## Phase 3 (official execution) status
### Attempted official inference path
- Planned official command pattern (from official Colab):
  1) download checkpoint from `arcinstitute/ST-HVG-Tahoe`;
  2) run `state tx infer` on AML with `--embed-key X_hvg`.

### Hard blocker encountered
- `snapshot_download(repo_id='arcinstitute/ST-HVG-Tahoe', ...)` failed with HTTP proxy 403.
- Without official model directory/checkpoint files, `state tx infer` cannot run.

## Task consequence
- CHEK1 knockdown virtual perturbation could not be executed in this container.
- Any claim about pathway up/down after CHEK1 KD would be non-official and speculative.
