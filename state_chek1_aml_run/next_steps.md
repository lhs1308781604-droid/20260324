# next_steps

## 为了完成“正式完整版”还缺什么
1. 让当前环境可访问 Hugging Face（至少这两个域名）：
   - `huggingface.co`
   - `cdn-lfs.huggingface.co`
2. 或者你离线提供以下目录到本容器：
   - `SE-600M`（SE checkpoint目录）
   - `ST-HVG-Tahoe/fewshot/state_generalization_X_hvg`（ST checkpoint目录）
3. 若坚持“先训练 Replogle-ST”，请提供本地 Replogle 数据目录（与 TOML 中路径一致，或我可帮你重写 TOML 指向新路径）。

## snapshot_download 403 的可执行修复
- 网络/代理侧：放行上面两个 HF 域名。
- 认证侧（若需要）：`huggingface-cli login` 并设置 `HF_TOKEN`。
- 代理变量（企业网络常见）：配置 `HTTPS_PROXY` / `HTTP_PROXY` / `NO_PROXY`。
- 离线路线（最稳）：你在可联网机器下载后，把 checkpoint 目录上传到本容器本地路径。

## 文件就绪后我会立即继续
1. 跑 SE transform。
2. 跑 Replogle-ST 训练（或你允许时用官方 ST 预训练后备版）。
3. 跑 AML CHEK1 inference。
4. 输出通路/关键基因方向并给出三选一结论。
