# official_state_auditor 输出（单代理退化执行）

> 说明：当前环境未提供可调用的 Codex subagents/custom agents 接口，本次按单代理执行，并按你要求保留角色化结构。

## 官方来源核对
- 官方仓库：ArcInstitute/state（已本地克隆到 `external_state_repo/`）。
- 官方 README 入口：
  - Replogle-ST 训练：`state tx train`（README 中 `train` 章节）
  - ST inference：`state tx infer`（README 中 `infer` 章节）
  - SE 入口：`state emb fit` / `state emb transform`
- 官方 notebook（README 链接对应 Colab）：
  - ST inference notebook 使用 `arcinstitute/ST-HVG-Tahoe` checkpoint，并以 `state tx infer` 做推理。

## 与本任务最相关的官方 CLI
- `state emb transform`：把输入数据转到 embedding 空间（通常产出 `obsm` embedding）。
- `state tx train`：按官方配置训练 ST（可按 Replogle split config）。
- `state tx infer`：在新数据上做虚拟扰动推理，关键参数包括：
  - `--model-dir`
  - `--checkpoint`
  - `--adata`
  - `--embed-key`
  - `--pert-col`
  - `--batch-col`
  - `--control-pert`

## 本任务“最官方完整路线”判断
优先应为：
1. **SE 纳入**：优先用官方预训练 SE checkpoint 做 transform；
2. **ST 训练**：按官方 Replogle-ST 训练流程（`state tx train`）；
3. **AML 推理**：在 AML 上用同路线预处理 + `state tx infer`，设定 CHEK1 KD。

### 是否需要自己训练 SE
- 通常不需要。官方更常见/更现实是使用预训练 SE checkpoint 做 transform。
- 自训 SE 计算与数据成本高，不是该任务最优先路径；使用官方预训练 checkpoint仍符合“官方标准流程”。

## 当前实际可执行性
- 你指定的输入路径 A/B 在当前云端容器均不存在（已核查）。
- 按你的硬性规则：A/B 都不存在时，必须停止正式训练和推理。
- 因此本次仅完成“官方流程核对 + 环境诊断”，不进行正式 SE/ST/CHEK1 推理。
