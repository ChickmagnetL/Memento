# Manual E2E Testing - Phase 1

## Prerequisites

- Python 3.10+ installed
- Node.js 18+ installed
- Backend dependencies installed (`cd backend && pip install -r requirements-dev.txt`)
- Frontend dependencies installed (`cd frontend && npm install`)

## Automated Checks

From the project root:

```bash
cd backend
source venv/bin/activate
pytest

cd ../frontend
npm run lint

cd ..
./scripts/smoke-test.sh
```

## Test Procedure

### 1. Start Backend

Terminal 1:
```bash
cd backend
source venv/bin/activate  # Windows: venv\Scripts\activate
uvicorn main:app --port 8000
```

Expected: Server starts with log message "Databases initialized at ..."

### 2. Start Frontend

Terminal 2:
```bash
cd frontend
npm run dev
```

Expected: Dev server starts on http://localhost:3000

### 3. Verify Frontend

Open browser: http://localhost:3000

Expected:
- Page displays "Memento" title
- Shows "Backend health: ok"

### 4. Verify Backend API Docs

Open browser: http://localhost:8000/docs

Expected:
- Swagger UI loads successfully
- Shows `/api/health` endpoint
- Can execute the endpoint and receive `{"status":"ok","service":"memento-backend"}`

## Phase 1 Acceptance Criteria

- [x] Frontend accessible at http://localhost:3000
- [x] Backend API docs at http://localhost:8000/docs
- [x] Health check endpoint returns 200
- [x] Configuration loads from YAML
- [x] Databases initialize without errors

All criteria should be verified with the automated checks above plus the manual browser checks.

## Phase 2A Checks

1. Start backend: `cd backend && source venv/bin/activate && uvicorn main:app --port 8000`
2. Start frontend: `cd frontend && npm run dev`
3. Open http://localhost:3000
4. Submit `https://www.bilibili.com/video/BV1234567890`
5. Expected: a pending Bilibili record appears and remains after refresh.
6. Submit `https://example.com/video/1`
7. Expected: unsupported URL error appears.

## Phase 2B Checks

These manual checks document the historical pre-Phase-2C behavior, when
processing used a placeholder workflow. Use the Phase 2C section below for
current manual validation.

Run automated checks from the project root:

```bash
cd backend
source venv/bin/activate
pytest

cd ../frontend
npm run lint
```

1. Start backend: `cd backend && source venv/bin/activate && uvicorn main:app --port 8000`
2. Start frontend: `cd frontend && npm run dev`
3. Open http://localhost:3000
4. Submit `https://www.bilibili.com/video/BV1234567890`
5. Use the processing action on the saved record.
6. Historical expected result: the record status changes to `completed`.
7. Expected: real subtitle extraction, video download, ASR, and OCR are not required for Phase 2B.

## Manual E2E Testing - Phase 2C

Manual success requires live Bilibili network/API access and a Bilibili video
with available soft subtitles. Old or public subtitles may work without a
cookie, but Bilibili AI subtitles often require an explicit local cookie. A
correct app can mark records as `failed` when subtitles, required cookies, or
network access are unavailable.

For local AI subtitle testing, prefer an environment variable and restart the
backend after setting it:

```bash
export VIDEO_PROCESSING__BILIBILI_COOKIE='SESSDATA=your-cookie; bili_jct=...'
```

Do not commit real cookie values. If you use `config.local.yaml` instead, keep
it local and out of version control.

1. Start backend: `cd backend; source venv/bin/activate; uvicorn main:app --port 8000`
2. Start frontend: `cd frontend; npm run dev`
3. Open http://localhost:3000.
4. Submit a Bilibili URL that has soft subtitles.
5. Click `Process`.
6. Confirm record becomes `completed`.
7. Confirm Markdown draft exists under `~/memento_data/knowledge/bilibili/`.
8. Submit or process a Douyin record.
9. Confirm it becomes `failed` in Phase 2C.

## MVP E2E 冒烟

`scripts/e2e-mvp.sh` 是一个面向发布前验证的端到端冒烟脚本，它会针对
**正在运行的整套栈** 完整跑通：导入视频 → 处理 → 生成文档 → 建索引 →
检索 → 聊天 SSE。它不是 CI 用脚本，也不会被最终用户看到，仅供开发者在
正式发布前手动执行。

### 前置条件

- 后端已启动并监听 `:8000`（`uvicorn main:app --port 8000`）。
- 已配置可用的 chat 与 embedding 模型（真实大模型，非 stub）。
- 本机已安装 `jq`。
- 准备一个**带 CC 字幕**的 Bilibili 视频链接。如该视频依赖 AI 字幕，
  请按 Phase 2C 章节设置 `VIDEO_PROCESSING__BILIBILI_COOKIE` 后重启后端。

### 执行命令

从项目根目录：

```bash
./scripts/e2e-mvp.sh "<bilibili-url-with-cc-subtitles>"
```

可通过环境变量覆盖后端地址，例如：

```bash
BASE_URL=http://localhost:8000 ./scripts/e2e-mvp.sh "<url>"
```

### 期望输出

脚本依次打印每个步骤标题，并在最后输出：

```
==> ALL PASSED
```

任一步骤失败时脚本立即退出（`set -euo pipefail`），并打印
`FAIL: ...` 行说明失败点（如 process status、no document、not indexed、
no search hits、no done event、error event）。

### 失败排查

若脚本在 Health 之前或某一步骤失败，先确认模型与后端状态：

```bash
curl -sf http://localhost:8000/api/settings/status | jq .
```

该接口会汇报 chat / embedding 模型与后端整体健康情况，是定位
“模型未配置 / 后端未就绪” 类问题的首要入口。随后可对照脚本中的步骤，
单独重放对应的 `curl` 请求以缩小问题范围。
