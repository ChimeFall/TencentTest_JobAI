# frontend

React + Vite 前端。启动和构建命令见根目录 README。

- `src/pages/` 四个页面：上传 / 对话 / 结果 / 优化
- `src/api.js` 封装了所有后端请求，统一走 axios 实例
- 开发时 `/api` 由 Vite 代理到本地 8000 端口，不用配跨域
