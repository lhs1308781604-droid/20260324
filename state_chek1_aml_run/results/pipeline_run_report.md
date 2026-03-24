# state_pipeline_runner 输出（单代理退化执行）

## 执行状态总览
- 目标流程：SE -> Replogle-ST 训练 -> AML CHEK1 推理
- 实际状态：**未启动正式流水线**（遵循你的规则，因输入路径 A/B 不存在）

## 已完成
1. 官方路线与命令核对（README、notebook、CLI）。
2. 环境依赖可用性检查。
3. 输入路径存在性检查（A/B 均不存在）。

## 未执行（并说明原因）
1. SE transform：未执行（无可访问输入文件）。
2. Replogle-ST 训练：未执行（按任务规则，输入不可访问时停止正式流程）。
3. AML CHEK1 inference：未执行（同上）。

## 与 403 相关的补充诊断
- 即便后续补齐输入文件，当前环境对 Hugging Face API 存在代理 403 风险，可能阻断官方 checkpoint 下载。
- 这会影响官方 notebook 中 `snapshot_download(repo_id='arcinstitute/ST-HVG-Tahoe', ...)`。
