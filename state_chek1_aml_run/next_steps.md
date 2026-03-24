# next_steps

## 先解决输入文件可访问性（必须）
你需要任选其一：
1. 把 `.h5ad` 上传到当前容器可访问路径（例如 `/workspace/20260324/AML_D0_for_State_beginner.h5ad`）；
2. 提供可直接下载链接（无需登录）；
3. 把文件放到你在本容器里可访问的绝对路径，并告诉我。

## 再解决 Hugging Face 403（checkpoint 下载）
针对 `snapshot_download(... ST-HVG-Tahoe ...)` 的 403，可按优先顺序：
1. **网络侧放行**：让当前执行环境允许访问 `https://huggingface.co` 与 `https://cdn-lfs.huggingface.co`。
2. **设置代理白名单**：在代理/防火墙中放行上述域名。
3. **改为离线交付 checkpoint**：由你在可联网机器下载后上传到容器，再本地 `--model-dir/--checkpoint` 指向该目录。
4. **如仓库需要鉴权**：配置 `HF_TOKEN`（`huggingface-cli login` 或环境变量）后重试。
5. **企业代理场景**：显式配置 `HTTPS_PROXY/HTTP_PROXY/NO_PROXY` 并重试。

## 当文件与checkpoint都可访问后，我会执行的正式版清单
1. 官方 SE transform（优先官方预训练 SE checkpoint）。
2. 官方 Replogle-ST 训练（保存 config/log/checkpoint）。
3. AML CHEK1 inference（记录模型、checkpoint、embed_key、pert设置）。
4. 仅围绕 MVA/胆固醇通路与关键基因输出“支持下降 / 不支持下降 / 证据不足”。
