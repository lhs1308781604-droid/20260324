# official_route

## 官方入口核对（ArcInstitute/state）
- Replogle-ST 训练入口：`state tx train`
- SE 入口：`state emb preprocess` / `state emb fit` / `state emb transform`
- ST inference 入口：`state tx infer`

## 本任务最官方完整路线（按你要求）
1. **SE**：优先官方预训练 checkpoint（SE-600M）做 `state emb transform`。
2. **ST**：按 Replogle 数据+TOML split 做 `state tx train`。
3. **AML 推理**：对 AML 做一致预处理后，`state tx infer` 做 CHEK1 KD。

## 本次实际可执行性
- SE checkpoint 官方 notebook 指向 Hugging Face `arcinstitute/SE-600M`，当前环境下载失败（403）。
- ST 官方 inference checkpoint（例如 `arcinstitute/ST-HVG-Tahoe`）下载也失败（403）。
- Replogle-ST 从头训练还需要本地可用 Replogle 数据目录（示例 TOML 使用 `/data/replogle_nogwps_v2`），当前不存在。
