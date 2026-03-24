# env_and_input_checker 输出（单代理退化执行）

## 环境检查
- 工作目录：`/workspace/20260324`
- OS：Ubuntu 24.04.3 LTS
- Python / uv / pip / git：均可用
- GPU：`nvidia-smi` 不可用（当前未见可用 NVIDIA GPU 工具）
- 磁盘：`/` 可用约 14G
- 网络：可访问 GitHub；网络可用但存在代理策略限制（后续对 Hugging Face API 出现 403）

## 输入文件路径核对（你指定的两条）
- A：`/content/drive/MyDrive/AML_D0_for_State_beginner.h5ad` -> **不存在**
- B：`/Users/liuhuashuo/Documents/生信数据/单细胞/AML_D0_for_State_beginner.h5ad` -> **不存在**

## 结论（按你的硬规则）
- A/B 均不存在，因此必须停止正式训练和推理。
- 当前仅允许继续做官方流程核对与环境诊断（本报告与 `official_route.md` 已完成）。
