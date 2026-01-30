# AES-GCM 任务模板 (Plan)

## 目标
生成 AES-GCM simple 示例，并通过 workflow_runner 验证。

## 推荐 Plan
1) 调用 ta_generator
   - name=aesgcm
   - template=aes_gcm_simple
   - output_dir=<workspace>
2) 调用 ca_generator
   - name=aesgcm
   - ta_name=aesgcm
   - template=aes_gcm_simple
   - output_dir=<workspace>
3) 调用 workflow_runner
   - ta_dir=<workspace>/aesgcm_ta
   - ca_dir=<workspace>/aesgcm_ca
   - timeout=180
