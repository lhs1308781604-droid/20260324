# Official Route (Arc State) for this task

## Official sources used
1. ArcInstitute/state official README (`external_state_repo/README.md`).
2. Official ST inference Colab downloaded from README link (`st_infer_colab.ipynb`).
3. Official CLI help from installed `state` package (`state --help`, `state tx --help`, `state emb --help`, `state tx infer --help`).

## Required official entry points (as requested)
- **SE entry**: `state emb fit`, `state emb transform`.
- **Replogle-ST training entry**: `state tx train` with TOML split config (README examples/fewshot.toml).
- **ST inference entry**: `state tx infer --model-dir ... --checkpoint ... --adata ... --pert-col ... --embed-key ...`.

## Most official, reasonable full route for this AML task
1. **SE handling**
   - Preferred official route is to use **official pretrained SE checkpoint** for embedding new data (`state emb transform`), rather than training SE from scratch.
   - Reason: SE pretraining is large-scale and not practical to retrain for a single inference task.
2. **ST handling**
   - Official examples show ST training via `state tx train` (often Replogle split configs).
   - For this task, the most direct official route is to use an **official pretrained ST checkpoint** and run `state tx infer` on AML data.
3. **Notebook-validated inference route**
   - Official Colab for Tahoe inference downloads `arcinstitute/ST-HVG-Tahoe` checkpoint and runs `state tx infer` with `X_hvg`.
4. **Why not train SE/ST from scratch here**
   - Not necessary for single-target inference if official pretrained inference checkpoint is available.
   - Also computationally expensive and beyond this container's practical limits.

## Blocking issue in this container
- Hugging Face model download (official checkpoint source used by official Colab) fails with proxy `403 Forbidden`.
- Therefore the official pretrained ST checkpoint cannot be obtained here, and official `state tx infer` cannot be completed to produce CHEK1 KD simulation outputs.
