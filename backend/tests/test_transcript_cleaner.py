"""Tests for AI transcript cleaning."""

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

SUMMARY_AND_BRIEF = (
    "<summary>本视频介绍青蒿素的来源，说明青蒿素是从黄花蒿中提取出来的，"
    "涉及的生物学背景包括黄花蒿的分布与药用历史。</summary>\n"
    "<brief>介绍青蒿素从黄花蒿中提取的过程。</brief>"
)

CLEANED_BODY = """## 青蒿素的来源

[00:01] 青蒿素是从黄花蒿中提取出来的。

""" + SUMMARY_AND_BRIEF


class FakeChatClient:
    def __init__(self, reply: str):
        self.reply = reply
        self.messages: list[list[dict]] = []

    def complete(self, messages: list[dict]) -> str:
        self.messages.append(messages)
        return self.reply


def test_clean_sends_transcript_and_wraps_result():
    chat = FakeChatClient(CLEANED_BODY)
    cleaner = TranscriptCleaner(chat_client=chat)

    cleaned = cleaner.clean(RAW_DRAFT)

    # Prompt carries the raw transcript body.
    sent = chat.messages[0]
    assert sent[0]["role"] == "system"
    assert "[00:01] 嗯就是说这个青蒿素呢它其实" in sent[1]["content"]
    # Output keeps the original header block and replaces the body.
    assert cleaned.startswith("# 示例视频")
    assert "- Video ID: v1" in cleaned
    assert "## 青蒿素的来源" in cleaned
    assert "[00:01] 青蒿素" in cleaned
    assert "嗯就是说" not in cleaned
    assert "<summary>" not in cleaned
    assert "<brief>" not in cleaned


def test_clean_rejects_output_that_drops_all_timestamps():
    chat = FakeChatClient("## 总结\n\n没有时间戳的内容。\n" + SUMMARY_AND_BRIEF)
    cleaner = TranscriptCleaner(chat_client=chat)

    with pytest.raises(CleaningError):
        cleaner.clean(RAW_DRAFT)


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
    chat = FakeChatClient("## Cleaned\n\n[00:01] Cleaned text.\n" + SUMMARY_AND_BRIEF)
    cleaner = TranscriptCleaner(chat_client=chat)

    cleaned = cleaner.clean(draft_no_marker)

    # The entire draft should be sent as user content
    sent = chat.messages[0]
    assert sent[1]["content"] == "Just some raw transcript text without headers."
    assert cleaned == "## Cleaned\n\n[00:01] Cleaned text.\n"


def test_clean_allows_body_without_timestamps():
    draft_no_ts = "# Video\n\n## Transcript\n\nPlain text without timestamps."
    chat = FakeChatClient(
        "## Cleaned\n\nCleaned text without timestamps.\n" + SUMMARY_AND_BRIEF
    )
    cleaner = TranscriptCleaner(chat_client=chat)

    # Should NOT raise CleaningError since original had no timestamps
    cleaned = cleaner.clean(draft_no_ts)
    assert "Cleaned text without timestamps" in cleaned


def test_clean_with_summary_produces_summary_and_brief():
    chat = FakeChatClient(CLEANED_BODY)
    cleaner = TranscriptCleaner(chat_client=chat)

    cleaned, l2_summary, l3_brief = cleaner.clean_with_summary(RAW_DRAFT)

    assert "青蒿素" in l2_summary
    assert "青蒿素" in l3_brief
    assert "<summary>" not in cleaned
    assert "<brief>" not in cleaned
    assert "## 青蒿素的来源" in cleaned


def test_clean_with_summary_rejects_missing_tags():
    chat = FakeChatClient("## 青蒿素的来源\n\n[00:01] 青蒿素。\n")
    cleaner = TranscriptCleaner(chat_client=chat)

    with pytest.raises(CleaningError):
        cleaner.clean_with_summary(RAW_DRAFT)
