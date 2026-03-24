# input_environment_report

## 阶段1：环境与工具
- 工作目录：`/workspace/20260324`
- OS：Ubuntu 24.04.3 LTS
- Python：3.10.19
- uv：0.7.22
- pip：25.3
- git：2.43.0
- GPU：`nvidia-smi` 不可用（当前容器无可见 NVIDIA 工具）
- 磁盘：可用约 14G
- 网络：GitHub 可访问；Hugging Face 访问受代理限制（403）

## 输入文件可访问性
- 你最新提供的链接可下载：
  - `AML_D0_for_State_beginner.h5ad`（已下载到 `/workspace/20260324/AML_D0_for_State_beginner.h5ad`）
- 原文件在当前环境下读取时遇到 `uns/log1p/base` 编码兼容问题。
- 已生成兼容副本：`/workspace/20260324/AML_D0_for_State_beginner_clean.h5ad`（仅移除 `uns/log1p/base`）。
