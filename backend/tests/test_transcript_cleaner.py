"""Tests for AI transcript cleaning."""

import json

import pytest

from core.video.cleaner import CLEANING_SYSTEM_PROMPT, CleaningError, TranscriptCleaner

RAW_DRAFT = """# 示例视频

- Platform: bilibili
- Video ID: v1
- Source URL: https://www.bilibili.com/video/BV1abc

## Transcript

[00:01] 嗯就是说这个青蒿素呢它其实
[00:05] 它是从黄花蒿里面提取出来的
"""

SUMMARY_TEXT = (
    "本视频介绍青蒿素的来源，说明青蒿素是从黄花蒿中提取出来的，"
    "涉及的生物学背景包括黄花蒿的分布与药用历史。"
)
BRIEF_TEXT = "介绍青蒿素从黄花蒿中提取的过程。"
CLEANED_TEXT = "[00:01] 青蒿素其实\n[00:05] 它是从黄花蒿里面提取出来的。"
MERGED_CLEANED_TEXT = "[00:01] 青蒿素其实，它是从黄花蒿里面提取出来的。"


class FakeChatClient:
    def __init__(self, reply: str):
        self.reply = reply
        self.messages: list[list[dict]] = []

    def complete(self, messages: list[dict]) -> str:
        self.messages.append(messages)
        return self.reply


def build_timestamped_reply(
    cleaned_text: str,
    *,
    summary: str = SUMMARY_TEXT,
    brief: str = BRIEF_TEXT,
    **extra,
) -> str:
    payload = {
        "cleaned_text": cleaned_text,
        "summary": summary,
        "brief": brief,
        **extra,
    }
    return json.dumps(payload, ensure_ascii=False)


def build_plain_reply(
    cleaned_text: str,
    *,
    summary: str = SUMMARY_TEXT,
    brief: str = BRIEF_TEXT,
    **extra,
) -> str:
    payload = {
        "cleaned_text": cleaned_text,
        "summary": summary,
        "brief": brief,
        **extra,
    }
    return json.dumps(payload, ensure_ascii=False)


def wrap_in_fence(reply: str, language: str = "json") -> str:
    opening_fence = f"```{language}" if language else "```"
    return f"{opening_fence}\n{reply}\n```"


def test_timestamped_clean_prompt_describes_relaxed_timestamp_rules():
    assert "Return valid JSON only" in CLEANING_SYSTEM_PROMPT
    assert "no markdown fence" in CLEANING_SYSTEM_PROMPT
    assert "cleaned_text" in CLEANING_SYSTEM_PROMPT
    assert "summary" in CLEANING_SYSTEM_PROMPT
    assert "brief" in CLEANING_SYSTEM_PROMPT
    assert "multi-line [timestamp] cleaned text" in CLEANING_SYSTEM_PROMPT
    assert "timestamps must be copied from the source only" in CLEANING_SYSTEM_PROMPT
    assert "only adjacent subtitle lines may be merged" in CLEANING_SYSTEM_PROMPT
    assert "at most two source subtitle lines" in CLEANING_SYSTEM_PROMPT
    assert "never three or more" in CLEANING_SYSTEM_PROMPT
    assert "merged output uses the earlier timestamp" in CLEANING_SYSTEM_PROMPT
    assert "do not move text far from the original timestamp" in CLEANING_SYSTEM_PROMPT
    assert "filler or meaningless lines may be deleted" in CLEANING_SYSTEM_PROMPT


def test_clean_sends_timestamped_body_and_accepts_fewer_lines():
    chat = FakeChatClient(build_timestamped_reply(MERGED_CLEANED_TEXT))
    cleaner = TranscriptCleaner(chat_client=chat)

    cleaned = cleaner.clean(RAW_DRAFT)

    sent = chat.messages[0]
    assert sent[0]["role"] == "system"
    assert sent[1]["content"] == (
        "[00:01] 嗯就是说这个青蒿素呢它其实\n"
        "[00:05] 它是从黄花蒿里面提取出来的"
    )
    assert cleaned.startswith("# 示例视频")
    assert "- Video ID: v1" in cleaned
    assert "[00:01] 青蒿素其实，它是从黄花蒿里面提取出来的。" in cleaned
    assert "[00:05]" not in cleaned
    assert "嗯就是说" not in cleaned


def test_clean_rejects_empty_draft():
    cleaner = TranscriptCleaner(chat_client=FakeChatClient("x"))
    with pytest.raises(ValueError):
        cleaner.clean("   ")


def test_clean_propagates_chat_errors():
    from core.models.chat_completion import ChatCompletionError

    class RaisingChatClient:
        def complete(self, messages: list[dict]) -> str:
            raise ChatCompletionError("API down")

    cleaner = TranscriptCleaner(chat_client=RaisingChatClient())
    with pytest.raises(ChatCompletionError):
        cleaner.clean(RAW_DRAFT)


def test_clean_handles_draft_without_transcript_marker():
    draft_no_marker = "Just some raw transcript text without headers."
    chat = FakeChatClient(build_plain_reply("Cleaned text."))
    cleaner = TranscriptCleaner(chat_client=chat)

    cleaned = cleaner.clean(draft_no_marker)

    sent = chat.messages[0]
    assert sent[1]["content"] == "Just some raw transcript text without headers."
    assert cleaned == "Cleaned text.\n"


def test_clean_allows_body_without_timestamps():
    draft_no_ts = "# Video\n\n## Transcript\n\nPlain text without timestamps."
    chat = FakeChatClient(build_plain_reply("Cleaned text without timestamps."))
    cleaner = TranscriptCleaner(chat_client=chat)

    cleaned = cleaner.clean(draft_no_ts)
    assert "Cleaned text without timestamps" in cleaned


def test_clean_accepts_plain_payload_wrapped_in_bare_code_fence():
    draft_no_marker = "Just some raw transcript text without headers."
    chat = FakeChatClient(
        wrap_in_fence(build_plain_reply("Cleaned text."), language="")
    )
    cleaner = TranscriptCleaner(chat_client=chat)

    cleaned = cleaner.clean(draft_no_marker)
    assert cleaned == "Cleaned text.\n"


def test_clean_with_summary_produces_summary_and_brief():
    chat = FakeChatClient(build_timestamped_reply(CLEANED_TEXT))
    cleaner = TranscriptCleaner(chat_client=chat)

    cleaned, l2_summary, l3_brief = cleaner.clean_with_summary(RAW_DRAFT)

    assert l2_summary
    assert l3_brief
    assert len(l2_summary) >= 10
    assert len(l3_brief) <= 60
    assert "[00:01] 青蒿素其实" in cleaned
    assert "[00:05] 它是从黄花蒿里面提取出来的。" in cleaned
    assert "青蒿素" in l2_summary
    assert "青蒿素" in l3_brief


def test_clean_with_summary_accepts_json_code_fence():
    chat = FakeChatClient(wrap_in_fence(build_timestamped_reply(CLEANED_TEXT)))
    cleaner = TranscriptCleaner(chat_client=chat)

    cleaned, l2_summary, l3_brief = cleaner.clean_with_summary(RAW_DRAFT)

    assert "[00:01] 青蒿素其实" in cleaned
    assert "[00:05] 它是从黄花蒿里面提取出来的。" in cleaned
    assert l2_summary == SUMMARY_TEXT
    assert l3_brief == BRIEF_TEXT


def test_clean_drops_timestamp_whose_text_is_empty():
    """无意义行可删除，对应时间戳同步消失。"""
    draft = """# 示例视频

## Transcript

[00:01] 哈喽大家好
[00:05] 呃那个那个那个
[00:08] 今天我们讲青蒿素
"""
    chat = FakeChatClient(
        build_timestamped_reply(
            "[00:01] 哈喽大家好。\n[00:08] 今天我们讲青蒿素。",
        )
    )
    cleaner = TranscriptCleaner(chat_client=chat)

    cleaned, _, _ = cleaner.clean_with_summary(draft)

    assert "[00:01] 哈喽大家好。" in cleaned
    assert "[00:05]" not in cleaned
    assert "[00:08] 今天我们讲青蒿素。" in cleaned


def test_clean_accepts_timestamped_reply_with_fewer_lines():
    draft = """# 示例视频

## Transcript

[00:01] 第一句很短
[00:02] 第二句也很短
[00:05] 第三句保留
"""
    chat = FakeChatClient(
        build_timestamped_reply("[00:01] 第一句很短，第二句也很短。\n[00:05] 第三句保留。")
    )
    cleaner = TranscriptCleaner(chat_client=chat)

    cleaned, _, _ = cleaner.clean_with_summary(draft)

    assert "[00:01] 第一句很短，第二句也很短。" in cleaned
    assert "[00:02]" not in cleaned
    assert "[00:05] 第三句保留。" in cleaned


def test_clean_rejects_timestamped_reply_with_unknown_timestamp():
    chat = FakeChatClient(
        build_timestamped_reply("[00:01] 青蒿素其实。\n[00:09] 生成的时间戳。")
    )
    cleaner = TranscriptCleaner(chat_client=chat)

    with pytest.raises(CleaningError, match="source timestamps"):
        cleaner.clean_with_summary(RAW_DRAFT)


def test_clean_rejects_timestamped_reply_without_timestamped_lines():
    chat = FakeChatClient(build_timestamped_reply("青蒿素其实。"))
    cleaner = TranscriptCleaner(chat_client=chat)

    with pytest.raises(CleaningError, match="timestamped lines"):
        cleaner.clean_with_summary(RAW_DRAFT)


def test_clean_with_summary_rejects_missing_summary_field():
    chat = FakeChatClient(
        json.dumps(
            {"cleaned_text": CLEANED_TEXT, "brief": BRIEF_TEXT},
            ensure_ascii=False,
        )
    )
    cleaner = TranscriptCleaner(chat_client=chat)

    with pytest.raises(CleaningError):
        cleaner.clean_with_summary(RAW_DRAFT)


def test_clean_with_summary_rejects_missing_brief_field():
    chat = FakeChatClient(
        json.dumps(
            {"cleaned_text": CLEANED_TEXT, "summary": SUMMARY_TEXT},
            ensure_ascii=False,
        )
    )
    cleaner = TranscriptCleaner(chat_client=chat)

    with pytest.raises(CleaningError, match="Missing `brief`"):
        cleaner.clean_with_summary(RAW_DRAFT)


def test_clean_with_summary_rejects_non_json_output():
    chat = FakeChatClient("not json")
    cleaner = TranscriptCleaner(chat_client=chat)

    with pytest.raises(CleaningError):
        cleaner.clean_with_summary(RAW_DRAFT)


def test_clean_rejects_output_with_extra_top_level_content():
    """顶部多了非约定 key → 报错（代码靠 key 区分三件套）。"""
    chat = FakeChatClient(
        build_timestamped_reply(CLEANED_TEXT, notes="## 青蒿素的来源")
    )
    cleaner = TranscriptCleaner(chat_client=chat)

    with pytest.raises(CleaningError):
        cleaner.clean_with_summary(RAW_DRAFT)


def test_clean_with_summary_retries_on_non_json_then_fails():
    """JSON 解析失败 → 自动重试一次 → 仍失败才报错。"""
    attempts = {"n": 0}

    class RetryClient:
        def complete(self, messages):
            attempts["n"] += 1
            return "not json even on retry"

    cleaner = TranscriptCleaner(chat_client=RetryClient())
    with pytest.raises(CleaningError):
        cleaner.clean_with_summary(RAW_DRAFT)
    assert attempts["n"] == 2


def test_clean_with_summary_retries_then_succeeds():
    """第一次非 JSON，第二次正常 → 成功。"""
    second = build_timestamped_reply(CLEANED_TEXT)

    class RetryClient:
        def __init__(self):
            self.calls = 0

        def complete(self, messages):
            self.calls += 1
            return "not json" if self.calls == 1 else second

    cleaner = TranscriptCleaner(chat_client=RetryClient())
    cleaned, _, _ = cleaner.clean_with_summary(RAW_DRAFT)
    assert "[00:01] 青蒿素其实" in cleaned


def test_clean_with_summary_retries_on_timestamp_validation_then_succeeds():
    valid_reply = build_timestamped_reply(CLEANED_TEXT)

    class RetryClient:
        def __init__(self):
            self.calls = 0

        def complete(self, messages):
            self.calls += 1
            if self.calls == 1:
                return build_timestamped_reply("[00:09] 青蒿素其实。")
            return valid_reply

    chat = RetryClient()
    cleaner = TranscriptCleaner(chat_client=chat)

    cleaned, _, _ = cleaner.clean_with_summary(RAW_DRAFT)

    assert chat.calls == 2
    assert "[00:01] 青蒿素其实" in cleaned
    assert "[00:05] 它是从黄花蒿里面提取出来的。" in cleaned


def test_plain_clean_retries_on_invalid_shape_then_succeeds():
    valid_reply = build_plain_reply("Cleaned text.")
    invalid_reply = json.dumps(
        {"lines": ["old shape"], "summary": SUMMARY_TEXT, "brief": BRIEF_TEXT},
        ensure_ascii=False,
    )

    class RetryClient:
        def __init__(self):
            self.calls = 0

        def complete(self, messages):
            self.calls += 1
            return invalid_reply if self.calls == 1 else valid_reply

    chat = RetryClient()
    cleaner = TranscriptCleaner(chat_client=chat)

    cleaned, _, _ = cleaner.clean_with_summary("Plain transcript without timestamps.")

    assert chat.calls == 2
    assert cleaned == "Cleaned text.\n"


def test_clean_with_summary_logs_parse_failure_clues(caplog):
    chat = FakeChatClient("```json\nnot json\n```")
    cleaner = TranscriptCleaner(
        chat_client=chat,
        diagnostic_context={
            "document_id": "d1",
            "source_path": "/tmp/v1.md",
        },
    )

    with caplog.at_level("WARNING", logger="core.video.cleaner"):
        with pytest.raises(CleaningError, match="valid JSON"):
            cleaner.clean_with_summary(RAW_DRAFT)

    assert "clean_payload_parse_failure" in caplog.text
    assert "'document_id': 'd1'" in caplog.text
    assert "'source_path': '/tmp/v1.md'" in caplog.text
    assert "'had_code_fence': True" in caplog.text
    assert "'json_errors':" in caplog.text
