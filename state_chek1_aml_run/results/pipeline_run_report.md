# pipeline_run_report

## 已完成（真实执行）
1. 下载输入文件：`AML_D0_for_State_beginner.h5ad`。
2. 兼容性清洗：生成 `AML_D0_for_State_beginner_clean.h5ad`。
3. 输入诊断：见 `state_chek1_aml_run/input_diagnostics.json`。
4. 官方预处理命令执行成功：
   - `state tx preprocess_train --adata AML_D0_for_State_beginner_clean.h5ad --output state_chek1_aml_run/results/aml_preprocessed_tx.h5ad --num_hvgs 2000`
   - 输出：`state_chek1_aml_run/results/aml_preprocessed_tx.h5ad`

## 尝试但失败
1. **SE checkpoint 下载失败**：`snapshot_download(repo_id='arcinstitute/SE-600M')` -> Proxy 403。
2. **ST checkpoint 下载失败**：`snapshot_download(repo_id='arcinstitute/ST-HVG-Tahoe')` -> Proxy 403。
3. **Replogle-ST 训练尝试失败**：
   - 使用官方 Replogle TOML（k562 split）启动训练。
   - 报错：`Dataset path does not exist: /data/replogle_nogwps_v2`，导致无训练集可用。

## 结果影响
- 未得到可用 ST checkpoint（无论预训练下载或本地训练）。
- 因此无法执行 AML 的 CHEK1 virtual perturbation inference（`state tx infer` 无模型可用）。
