"""Tests for AI transcript cleaning (compact text-array format)."""

import json

import pytest

from core.video.cleaner import CleaningError, TranscriptCleaner

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
# 新格式：模型只回「清洗后文字」，按原文顺序排。
CLEANED_TEXTS = ["青蒿素其实", "它是从黄花蒿里面提取出来的。"]


class FakeChatClient:
    def __init__(self, reply: str):
        self.reply = reply
        self.messages: list[list[dict]] = []

    def complete(self, messages: list[dict]) -> str:
        self.messages.append(messages)
        return self.reply


def build_timestamped_reply(
    texts: list[str],
    *,
    summary: str = SUMMARY_TEXT,
    brief: str = BRIEF_TEXT,
    **extra,
) -> str:
    """构造新格式回复：lines 是纯文字数组。"""
    payload = {
        "lines": list(texts),
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


def test_clean_sends_transcript_body_and_wraps_result():
    chat = FakeChatClient(build_timestamped_reply(CLEANED_TEXTS))
    cleaner = TranscriptCleaner(chat_client=chat)

    cleaned = cleaner.clean(RAW_DRAFT)

    sent = chat.messages[0]
    assert sent[0]["role"] == "system"
    assert "[00:01]" in sent[1]["content"]
    assert "嗯就是说这个青蒿素呢它其实" in sent[1]["content"]
    assert cleaned.startswith("# 示例视频")
    assert "- Video ID: v1" in cleaned
    assert "[00:01] 青蒿素其实" in cleaned
    assert "[00:05] 它是从黄花蒿里面提取出来的。" in cleaned
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
    chat = FakeChatClient(build_timestamped_reply(CLEANED_TEXTS))
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
    chat = FakeChatClient(wrap_in_fence(build_timestamped_reply(CLEANED_TEXTS)))
    cleaner = TranscriptCleaner(chat_client=chat)

    cleaned, l2_summary, l3_brief = cleaner.clean_with_summary(RAW_DRAFT)

    assert "[00:01] 青蒿素其实" in cleaned
    assert "[00:05] 它是从黄花蒿里面提取出来的。" in cleaned
    assert l2_summary == SUMMARY_TEXT
    assert l3_brief == BRIEF_TEXT


def test_clean_drops_timestamp_whose_text_is_empty():
    """空串 = 整句删除，对应时间戳同步消失。"""
    draft = """# 示例视频

## Transcript

[00:01] 哈喽大家好
[00:05] 呃那个那个那个
[00:08] 今天我们讲青蒿素
"""
    chat = FakeChatClient(
        build_timestamped_reply(
            ["哈喽大家好。", "", "今天我们讲青蒿素。"],
        )
    )
    cleaner = TranscriptCleaner(chat_client=chat)

    cleaned, _, _ = cleaner.clean_with_summary(draft)

    assert "[00:01] 哈喽大家好。" in cleaned
    assert "[00:05]" not in cleaned
    assert "[00:08] 今天我们讲青蒿素。" in cleaned


def test_clean_with_summary_rejects_missing_summary_field():
    chat = FakeChatClient(
        json.dumps(
            {"lines": CLEANED_TEXTS, "brief": BRIEF_TEXT},
            ensure_ascii=False,
        )
    )
    cleaner = TranscriptCleaner(chat_client=chat)

    with pytest.raises(CleaningError):
        cleaner.clean_with_summary(RAW_DRAFT)


def test_clean_with_summary_rejects_non_json_output():
    chat = FakeChatClient("not json")
    cleaner = TranscriptCleaner(chat_client=chat)

    with pytest.raises(CleaningError):
        cleaner.clean_with_summary(RAW_DRAFT)


def test_clean_rejects_output_with_extra_top_level_content():
    """顶部多了非约定 key → 报错（代码靠 key 区分三件套）。"""
    chat = FakeChatClient(
        build_timestamped_reply(CLEANED_TEXTS, notes="## 青蒿素的来源")
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
    second = build_timestamped_reply(CLEANED_TEXTS)

    class RetryClient:
        def __init__(self):
            self.calls = 0

        def complete(self, messages):
            self.calls += 1
            return "not json" if self.calls == 1 else second

    cleaner = TranscriptCleaner(chat_client=RetryClient())
    cleaned, _, _ = cleaner.clean_with_summary(RAW_DRAFT)
    assert "[00:01] 青蒿素其实" in cleaned


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
