# API Key 配置说明

请勿在仓库中保存任何真实密钥。实际密钥只应写入本地未提交的 `.env` 或部署平台环境变量。

## DeepSeek

- `DEEPSEEK_BASE_URL=https://api.deepseek.com/v1`
- `DEEPSEEK_API_KEY=sk-d3a1fe234c19415c9d2ad7ac679a3c72`
- 当前后端公开可选模型以运行时配置接口 `/api/config/models` 为准。

## MiMo

- `MIMO_BASE_URL=https://token-plan-cn.xiaomimimo.com/v1`
- `MIMO_API_KEY=tp-cztdvjv9a9vznv3ywko0z4meu68ufe8apmkkc1e8irw9m3g0`
- 当前后端公开可选模型以运行时配置接口 `/api/config/models` 为准。

## 推荐做法

- 本地开发：复制 `script-engine/.env.example` 为本地 `.env` 后填写真实值
- Render 部署：在 Dashboard 或 `render.yaml` 对应服务中单独注入密钥
- 密钥一旦误提交，必须立即轮换，不要继续复用旧值
