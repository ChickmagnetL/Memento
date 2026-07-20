# Chat 会话、编辑与停止

本文说明对话页的**会话生命周期**、**消息编辑/删除**、**生成中停止并回填** 的设计与前后端契约。知识检索工具与 Agent 指令拼装见 [记忆系统架构](./memory-architecture.md)；表落点见 [存储与检索](./storage-and-retrieval.md)。

---

## 目标能力

| 能力 | 用户侧表现 | 核心约束 |
|------|------------|----------|
| 会话时机 | 发出**第一条**消息时，侧栏立刻出现会话 | 前端先 `POST /api/sessions`，再带 `session_id` 流式聊天；不再依赖「答完才建会话」 |
| 编辑 | 改历史 **user** 气泡 → 截断后续 → 自动重生成 | 服务端改内容 + 删该条之后的消息；`regenerate=true` 不再重复落库 user |
| 删除 | 删一条 user 及其紧邻的 assistant | 服务端返回 `deleted[]`；前端据此更新；**删空则删会话** |
| 停止 | 生成中点 Stop / ESC → 半截回复消失、话回输入框 | 客户端 abort SSE；服务端 `CancelledError` **不**落库半截 assistant；前端再 best-effort 删本轮 user |

---

## 后端 API

### 会话

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/api/sessions` | 列表 |
| `POST` | `/api/sessions` | 新建（可空标题） |
| `PATCH` | `/api/sessions/{sid}` | 改标题（`{ title? }`；空 body 为 no-op） |
| `DELETE` | `/api/sessions/{sid}` | 删会话及其消息 |
| `GET` | `/api/sessions/{sid}/messages` | 消息列表（含 `id` / `role` / `content`） |

### 消息

| 方法 | 路径 | 说明 |
|------|------|------|
| `PATCH` | `/api/sessions/{sid}/messages/{mid}` | **仅 user**：更新 `content`，并 **删除该条之后** 的全部消息；若被编辑的是会话首条 user，标题按新内容截断刷新 |
| `DELETE` | `/api/sessions/{sid}/messages/{mid}` | **仅 user**：删除该条 + 若下一条是 assistant 则一并删；返回 `{ "deleted": [id, ...] }` |

非 user 角色编辑/删除 → `400`。消息不在该会话 → `404`。

### 聊天流

| 方法 | 路径 | 说明 |
|------|------|------|
| `POST` | `/api/chat` | SSE 流式生成 |

**请求要点**（`ChatRequest`）：

- **`session_id` 必填**（缺失 → `422`）。后端不再在聊天接口里隐式建会话。
- **`regenerate: bool = false`**：为 `true` 时**跳过**本轮 user 的 `add_chat_message`（编辑路径已由 PATCH 落库）。
- 正常路径：流开始前持久化 user；**仅成功结束**时持久化 assistant。
- 客户端断开 / 取消：`event_stream` 捕获 `asyncio.CancelledError` → INFO 日志 → **不**写半截 assistant、**不**发 `error` SSE → re-raise。

Storage 辅助（`SQLiteClient`）：`get_chat_message` / `update_chat_message` / `delete_chat_message` / `delete_messages_after`。

---

## 前端架构

### 模块

| 文件 | 职责 |
|------|------|
| `frontend/src/lib/api.ts` | `sendChatMessage`（`signal` / `regenerate`）、`editMessage` / `deleteMessage` / `updateSession` / `createSession` |
| `frontend/src/lib/chat-store.tsx` | 会话与消息状态、`sendMessage` / `editMessage` / `deleteMessage` / `retractLast` |
| `frontend/src/app/chat/chat-panel.tsx` | 列表 UI、编辑/删除控件、Stop 与 ESC、确认对话框 |
| `frontend/src/components/chat/delete-message-dialog.tsx` | 删消息确认（与删会话同风格的应用内弹窗） |

### 会话时机（废弃 `__new__` 桶）

1. 用户发送时若无 `activeId`：`createSession()` → `ADD_SESSION` + `SET_ACTIVE` → 侧栏立即可见。
2. 再带真实 `session_id` 调用 `sendChatMessage`。
3. `activeMessages` 仅在有 `activeId` 时读 `messagesBySession[id]`，不再使用 `"__new__"` 占位桶。

### 编辑

1. 乐观 `EDIT_MESSAGE`：改目标内容，并丢掉该 id **之后** 的本地消息。
2. `PATCH` 服务端；失败则 `getSessionMessages` 回滚。
3. `sendMessage(content, { regenerate: true })`：只追加空 assistant 气泡并流式填充，不重复 append user。
4. 生成中禁止进入编辑（store 守卫 + UI disabled）。

### 删除

1. 自定义对话框确认后调用 store `deleteMessage`。
2. 先 API，再用服务端 `deleted[]` 做 `DELETE_MESSAGES`（非乐观，避免失败回滚）。
3. 再 `getSessionMessages`：若会话已空 → `deleteSession` + 刷新列表 + `handleNew()`（侧栏去掉空话题）。

### 停止 / 回填（retract）

1. 生成中：composer 的 Send 位变为 **Stop**；全局 **ESC** 同样触发 `retractLast`（非生成时 no-op）。
2. `retractLast`：bump generation token（作废 in-flight 回调）→ abort `AbortController` → `RETRACT_LAST`（只剥**尾部** assistant + 最后一条 user，历史轮次保留）→ 内容写入 `composerInput`，panel 同步进输入框后清空 store 字段。
3. 服务端清理 best-effort：`client-*` 临时 id 先 `getSessionMessages` 按内容匹配再 DELETE；失败静默。用 `cleanupToken` 避免「撤回后立刻重发」误删新消息。
4. `retractingRef` 防止连点二次剥轮。

### 消息 id

- 列表 `key` 与编辑/删除目标均为 **message.id**。
- 乐观追加使用 `client-user-…` / `client-assistant-…`；流结束 `onDone` 用服务端列表整表水合替换。

---

## 时序简图

### 首条消息

```
UI send
  → POST /api/sessions          （侧栏立刻有会话）
  → POST /api/chat (session_id) （SSE；先落库 user，成功后落库 assistant）
  → onDone: GET messages + list sessions
```

### 编辑重生成

```
UI confirm edit
  → 本地 EDIT_MESSAGE（截断后续）
  → PATCH .../messages/{mid}
  → POST /api/chat { regenerate: true }
  → onDone 水合
```

### 停止

```
UI Stop / ESC
  → abort fetch（服务端 CancelledError，不落库 assistant）
  → 本地 RETRACT_LAST + 输入框回填
  → best-effort DELETE 本轮 user
```

---

## 不变量与边界

1. **只有 user 可编辑/删除**；assistant 内容靠「截断 + 重生成」间接替换。
2. **停止 ≠ 错误**：取消不写 error 事件，UI 不弹失败条。
3. **空会话不占侧栏**：删光消息后会话行应消失。
4. **长会话上下文仍无裁剪**：每次请求回放该会话全部历史（见记忆文档）；编辑/删除会改变回放集合。
5. **`/remember`** 仍不写会话历史；无活跃会话时不再写入已废弃的 `__new__` 桶。

---

## 相关代码入口

| 路径 | 说明 |
|------|------|
| `backend/api/sessions.py` | PATCH session / PATCH·DELETE message |
| `backend/api/chat.py` | `session_id` 必填、`regenerate`、`CancelledError` |
| `backend/storage/sqlite_client.py` | chat 消息 CRUD / truncate |
| `frontend/src/lib/chat-store.tsx` | 状态机与出口 |
| `frontend/src/app/chat/chat-panel.tsx` | 交互与布局 |
| `frontend/tests/chat-edit-stop-delete-ui.test.mjs` | 源码级契约测试 |

---

## 相关文档

- [记忆系统架构](./memory-architecture.md)
- [系统总览](./system-overview.md)
- [存储与检索](./storage-and-retrieval.md)
