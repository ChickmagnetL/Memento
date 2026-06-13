# Memento Douyin Fetcher Service

独立的数据获取服务，使用自己的 venv 隔离 F2（抖音 API 库），避免与主后端 pydantic 版本冲突。

## 安装

```bash
bash setup.sh
```

## 启动

```bash
cd services/douyin_fetcher
.venv/bin/uvicorn server:app --port 8002
```

服务默认监听端口 **8002**。API 文档自动生成在 `http://localhost:8002/docs`。

## 接口

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/health` | 健康检查 |
| POST | `/resolve` | 通过 aweme_id 获取视频播放地址 |

## 删除

```bash
rm -rf .venv
```
