# results_summary

## 你要求的分阶段进度
### 阶段1（官方流程+环境）
- 已完成官方 README/notebook/CLI 核对。
- 已确认工具可用（python/uv/pip/git）。
- 已确认 HF 下载受代理 403 限制。

### 阶段2（路线判断）
- 选定官方完整路线：SE(预训练) -> Replogle-ST训练 -> AML CHEK1 inference。
- 已明确为何当前无法完整跑通：checkpoint 下载受阻 + Replogle 数据目录缺失。

### 阶段3（输入诊断）
- 输入文件已通过你提供链接成功下载。
- 已完成诊断（human、gene symbol、X/obs/var齐全、含`layers['counts']`和`obsm['X_hvg']`）。

### 阶段4（SE）
- 已按官方方向定位 SE-600M checkpoint。
- 下载失败（403），SE transform 无法正式执行。

### 阶段5（Replogle-ST 训练）
- 已尝试按官方 Replogle TOML 启动训练。
- 失败：本地缺少 `/data/replogle_nogwps_v2`，无训练数据。

### 阶段6（AML 推理）
- 已完成官方 `tx preprocess_train` 生成 AML 预处理文件。
- 因无可用 ST checkpoint，CHEK1 inference 未执行。

### 阶段7（CHK1–MVA 假说）
- 最终结论：**证据不足 / 结果不稳定**（不伪造结果）。

## 是否成功使用 subagents
- 未成功。当前环境未提供可调用 subagent/custom-agent 接口，使用单代理执行。

## 输入与输出
- 输入：`/workspace/20260324/AML_D0_for_State_beginner.h5ad`
- 核心输出目录：`/workspace/20260324/state_chek1_aml_run/results/`
