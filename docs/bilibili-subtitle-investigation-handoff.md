# Bilibili 字幕失败排查交接

更新时间：2026-07-16

## 当前结论

问题尚未解决。

用户确认以下安装包仍然会持续弹出“没有可用字幕”：

- 最新 GitHub Actions 构建的 macOS 和 Windows 安装包。
- 本轮在 `fix/asr-transcription-bugs` worktree 本地重新构建的 macOS DMG。

不要再以“底层客户端能够拿到字幕”作为修复完成标准。必须从桌面界面走完整流程验证，包括字幕预检、视频处理管线和最终文档生成。

## 工作目录

- 主目录：`/Users/leo/development/memento`
- 修复 worktree：`/Users/leo/development/memento-asr-fixes`
- 分支：`fix/asr-transcription-bugs`

本轮结束时没有执行新的 Git 提交、合并或推送。

AGENTS.md 要求所有 Git 操作必须先获得用户明确批准。

## 用户观察

1. 最早本地构建的一份 DMG 可以稳定获取 Bilibili 字幕。
2. 后续 GitHub Actions 构建的 Windows 和 macOS 安装包都持续显示“没有可用字幕”。
3. 删除字幕预检接口中的 AI 字幕拦截后，本地重新构建 DMG，用户实测仍然失败。
4. 因此当前问题不只存在于字幕预检接口，处理管线或桌面运行时仍有其他拦截或版本复用问题。

已用于真实请求的视频：

- `https://www.bilibili.com/video/BV1kSsozkEEJ`

## 已确认的底层行为

使用应用现有登录状态直接调用 `BilibiliSubtitleClient.fetch_outcome`：

```text
has_subtitles: true
reason: ok
source: automatic
entry_count: 655
```

这说明至少在当前机器、当前 Cookie 和该视频上：

- WBI 播放器接口可以返回字幕。
- 字幕正文可以下载和解析。
- 失败发生在底层字幕客户端之后，或者桌面应用没有实际运行本次构建的后端。

不要在文档、日志或终端输出中记录 Cookie 内容。

## 两层 AI 字幕拦截

当前实现会把 Bilibili AI 字幕标记为 `source="automatic"`。此前至少存在两处把这种字幕重新判定为不可用的逻辑。

### 1. 字幕预检接口

文件：`backend/api/videos.py`

失败的 CI 包中，`GET /api/videos/{video_id}/check-subtitles` 会把：

```text
has_subtitles=true, reason=ok, source=automatic
```

改写为：

```text
has_subtitles=false, reason=no_subtitles
```

本轮已经在 worktree 中删除该改写，并调整了对应测试：

- `backend/api/videos.py`
- `backend/tests/test_videos_api.py`

这些修改尚未提交。

安装包字节码检查结果：

- 失败的 CI DMG：存在 `automatic_only`、`outcome_reason`、`outcome_message`。
- 本轮新 DMG：上述预检改写已不存在。

但是用户测试新 DMG 后仍然失败，因此这里只是问题的一部分。

### 2. 视频处理管线

文件：`backend/core/video/pipeline.py`

当前仍存在以下行为：

```python
entries = outcome.entries
if getattr(outcome, "source", None) == "automatic":
    entries = []
    empty_error = BilibiliSubtitleError(
        REASON_MESSAGES[REASON_NO_SUBTITLES],
        reason=REASON_NO_SUBTITLES,
    )
```

也就是说，即使字幕预检已经返回“有字幕”，实际处理阶段仍会主动清空 655 条 AI 字幕，然后生成 `no_subtitles` 错误。

这是下一会话应优先验证的根因。用户要求本轮不要继续修改，因此该处保持原样。

## 为什么最早的 DMG 可以工作

最早可用的本地 DMG 是一个中间构建版本：

- 已经使用 WBI 字幕接口。
- Bilibili 返回结果还没有 `source="automatic"` 分类，或者完整流程还没有根据该分类屏蔽字幕。
- 安装包内的字幕预检函数没有 `automatic_only` 改写。

因此同一条 Bilibili AI 字幕在旧包中被当作普通可用字幕，在后续版本中则被两层逻辑主动拒绝。

## 已做但不足以证明修复的验证

- Bilibili 相关测试：91 项通过。
- 后端全量测试：861 项通过。
- 真实底层请求：`BV1kSsozkEEJ` 获取 655 条字幕。
- PyInstaller 后端包含最新的 `backend/api/videos.py` 修改。
- DMG 内后端与构建目录中的后端 SHA-256 一致。

这些验证没有覆盖“从桌面弹窗到处理管线完成”的完整用户路径，因此不能作为问题已解决的证据。

现有测试曾明确要求 AI 字幕返回 `no_subtitles`，说明测试把错误产品行为固化成了通过条件。下一会话需要检查处理管线测试是否也存在相同问题。

## 本轮构建产物

本轮用户测试失败的 DMG：

```text
/Users/leo/development/memento-asr-fixes/desktop/dist/Memento-macOS.dmg
```

构建时间：`2026-07-16 03:06:12`

SHA-256：

```text
71341cd361a99d2f21231f1089322d92b02760249fea5157664f0cd306f28c7c
```

GitHub Actions 失败体验对应运行：

```text
https://github.com/ChickmagnetL/Memento/actions/runs/29439670112
```

该 CI 本身构建成功，但产品行为失败。

## 桌面后端复用风险

文件：`desktop/main.js`

桌面应用启动时会先检查 `http://127.0.0.1:8000/api/health`。如果该端口已有健康后端，应用不会启动安装包内的新后端。

这会导致测试新 DMG 时仍然连接旧版本后端。下一会话需要在复现前确认：

- 所有旧 Memento 进程已经退出。
- `8000` 端口没有残留后端。
- 当前运行进程的可执行文件路径来自正在测试的 `.app`。

不要只要求用户“退出旧应用”，需要实际检查进程和端口归属。

## 下一会话建议步骤

1. 不改代码，先在干净进程状态下复现一次。
2. 分别记录以下请求的实际 JSON 响应：
   - 创建 Bilibili 视频记录。
   - `GET /api/videos/{video_id}/check-subtitles`。
   - 视频处理请求。
3. 确认弹窗来自字幕预检失败，还是处理管线返回 `no_subtitles`。
4. 检查正在运行的后端二进制路径，排除旧后端占用 `8000` 端口。
5. 若确认 `backend/core/video/pipeline.py` 清空 AI 字幕是根因：
   - 先写一个真实流程级回归测试，要求 `source="automatic"` 的 655 条字幕进入文档生成路径。
   - 再做最小修改，禁止处理管线丢弃 Bilibili 自带 AI 字幕。
6. 重新构建 DMG 后，从桌面界面完成一次真实视频导入，确认文档中确实包含正确字幕，而不只是预检不弹窗。
7. 用户验证安装包成功后，再申请 Git 提交、合并和推送批准。

## 当前未提交修改

本轮已修改但未提交：

- `backend/api/videos.py`
- `backend/tests/test_videos_api.py`
- `docs/bilibili-subtitle-investigation-handoff.md`

不要丢弃这些修改。下一会话应先阅读差异并决定是保留预检修复，还是在完整流程修复后一起调整测试。

## 其他注意事项

- 当前 WBI 地址：`https://api.bilibili.com/x/player/wbi/v2`。
- 空字幕正文会继续轮换和重试，不会立即返回失败。
- 不要再次只用 mocked 单元测试或底层客户端探针宣布修复完成。
- 成功标准是用户界面导入真实 Bilibili 视频后，生成包含正确字幕的文档。
