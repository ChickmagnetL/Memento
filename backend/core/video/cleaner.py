"""AI transcript cleaning: fix errors, punctuation, and fillers.

Splits the 2C draft into header (title + metadata bullets) and body,
sends only the body to the LLM, and re-attaches the header so video
metadata is never mangled by the model.
"""

import json
import logging
import re

from core.models.chat_completion import ChatCompletionError


CLEANING_SYSTEM_PROMPT = (
    "You clean Chinese video transcripts. Rules:\n"
    "1. Return valid JSON only; no markdown fence.\n"
    "2. Output only `cleaned_text`, `summary`, and `brief`.\n"
    "3. When the input contains timestamped subtitle lines, return `cleaned_text` "
    "as multi-line [timestamp] cleaned text. All timestamps must be copied from "
    "the source only; never invent or modify timestamps.\n"
    "4. only adjacent subtitle lines may be merged. Merge at most two source "
    "subtitle lines into one output line; never three or more. The merged output "
    "uses the earlier timestamp. do not move text far from the original timestamp.\n"
    "5. filler or meaningless lines may be deleted (嗯/呃/那个那个那个 etc.).\n"
    "6. When the input is plain transcript text without timestamps, return plain "
    'cleaned text in `cleaned_text`.\n'
    "7. Clean Chinese ASR text by fixing recognition errors, adding punctuation, "
    "and removing filler words (嗯/啊/呃/额/就是说/那么 etc.) and repeated phrases.\n"
    "8. `summary` must be a 150-300 character paragraph summarizing the video. "
    "`brief` must be one sentence of 60 characters or fewer describing the topic."
)

TIMESTAMP_PATTERN = re.compile(r"\[(\d{1,2}:\d{2}(?::\d{2})?)\]")
LOG_SAMPLE_LIMIT = 160
logger = logging.getLogger(__name__)


class CleaningError(Exception):
    pass


def _compact_log_text(text: str, *, limit: int = LOG_SAMPLE_LIMIT) -> str:
    compact = " ".join(text.split())
    if len(compact) <= limit:
        return compact
    return f"{compact[: limit - 1]}…"


def _json_error_details(error: json.JSONDecodeError) -> str:
    return f"{error.msg} (line {error.lineno}, col {error.colno})"


def _sorted_object_keys(value: object) -> list[str] | None:
    if not isinstance(value, dict):
        return None
    return sorted(str(key) for key in value)


def _merge_log_context(
    log_context: dict[str, object] | None,
    **fields: object,
) -> dict[str, object]:
    context = dict(log_context or {})
    for key, value in fields.items():
        if value is None:
            continue
        context[key] = value
    return context


def _log_clean_failure(
    event: str,
    *,
    log_context: dict[str, object] | None = None,
    **fields: object,
) -> None:
    logger.warning("%s %s", event, _merge_log_context(log_context, **fields))


def _timestamped_lines(text: str) -> list[tuple[str, str]]:
    lines = []
    for line in text.splitlines():
        match = TIMESTAMP_PATTERN.search(line)
        if match:
            lines.append((match.group(1), line[match.end() :].strip()))
    return lines


def _unwrap_json_code_fence(raw_output: str) -> str:
    lines = raw_output.strip().splitlines()
    if len(lines) < 3:
        return raw_output

    opening_fence = lines[0].strip()
    closing_fence = lines[-1].strip()
    if closing_fence != "```" or not opening_fence.startswith("```"):
        return raw_output

    fence_language = opening_fence[3:].strip().lower()
    if fence_language not in {"", "json"}:
        return raw_output

    return "\n".join(lines[1:-1]).strip()


def _load_cleaned_payload(
    raw_output: str,
    *,
    log_context: dict[str, object] | None = None,
) -> dict:
    payload = None
    last_error = None
    json_errors: dict[str, str] = {}
    candidates = [("raw", raw_output)]
    unwrapped_output = _unwrap_json_code_fence(raw_output)
    if unwrapped_output != raw_output:
        candidates.append(("unwrapped", unwrapped_output))
    for candidate_name, candidate in candidates:
        try:
            payload = json.loads(candidate)
            break
        except json.JSONDecodeError as exc:
            last_error = exc
            json_errors[candidate_name] = _json_error_details(exc)
    if payload is None:
        _log_clean_failure(
            "clean_payload_parse_failure",
            log_context=log_context,
            had_code_fence=unwrapped_output != raw_output,
            json_errors=json_errors,
        )
        raise CleaningError("Cleaned output must be valid JSON") from last_error
    if not isinstance(payload, dict):
        _log_clean_failure(
            "clean_payload_type_failure",
            log_context=log_context,
            had_code_fence=unwrapped_output != raw_output,
            payload_type=type(payload).__name__,
        )
        raise CleaningError("Cleaned output must be a JSON object")
    return payload


def _extract_text_field(
    payload: dict,
    field: str,
    *,
    log_context: dict[str, object] | None = None,
) -> str:
    value = payload.get(field)
    if not isinstance(value, str) or not value.strip():
        _log_clean_failure(
            "clean_payload_field_failure",
            log_context=log_context,
            missing_field=field,
            top_level_keys=_sorted_object_keys(payload),
            field_type=type(value).__name__,
        )
        raise CleaningError(f"Missing `{field}` in cleaned output")
    return value.strip()


def _assert_cleaned_payload(
    raw_output: str,
    *,
    source_body: str | None = None,
    log_context: dict[str, object] | None = None,
) -> dict:
    """Validate payload shape enough to decide whether to retry the model call."""
    payload = _load_cleaned_payload(raw_output, log_context=log_context)
    _extract_text_field(payload, "summary", log_context=log_context)
    _extract_text_field(payload, "brief", log_context=log_context)
    if source_body is not None:
        _validate_timestamped_payload(source_body, payload, log_context=log_context)
        return payload
    _validate_plain_payload(payload, log_context=log_context)
    return payload


def _validate_timestamped_payload(
    source_body: str,
    payload: dict,
    *,
    log_context: dict[str, object] | None = None,
) -> str:
    source_lines = _timestamped_lines(source_body)
    if not source_lines:
        raise CleaningError("Source body does not contain timestamps")

    if set(payload) != {"cleaned_text", "summary", "brief"}:
        _log_clean_failure(
            "clean_timestamped_shape_failure",
            log_context=log_context,
            top_level_keys=_sorted_object_keys(payload),
        )
        raise CleaningError(
            "Cleaned output must contain only `cleaned_text`, `summary`, and `brief`"
        )

    cleaned_text = _extract_text_field(
        payload, "cleaned_text", log_context=log_context
    )
    output_timestamps = TIMESTAMP_PATTERN.findall(cleaned_text)
    if not output_timestamps:
        _log_clean_failure(
            "clean_timestamped_missing_lines",
            log_context=log_context,
        )
        raise CleaningError("Cleaned output must contain timestamped lines")

    source_timestamps = {timestamp for timestamp, _ in source_lines}
    unknown_timestamps = [
        timestamp for timestamp in output_timestamps if timestamp not in source_timestamps
    ]
    if unknown_timestamps:
        _log_clean_failure(
            "clean_timestamped_source_mismatch",
            log_context=log_context,
            unknown_timestamps=unknown_timestamps,
        )
        raise CleaningError(
            "Cleaned output timestamps must come from source timestamps"
        )
    return cleaned_text


def _validate_plain_payload(
    payload: dict,
    *,
    log_context: dict[str, object] | None = None,
) -> str:
    if set(payload) != {"cleaned_text", "summary", "brief"}:
        _log_clean_failure(
            "clean_plain_payload_shape_failure",
            log_context=log_context,
            top_level_keys=_sorted_object_keys(payload),
        )
        raise CleaningError(
            "Cleaned output must contain only `cleaned_text`, `summary`, and `brief`"
        )
    cleaned_text = payload.get("cleaned_text")
    if not isinstance(cleaned_text, str):
        _log_clean_failure(
            "clean_plain_payload_shape_failure",
            log_context=log_context,
            top_level_keys=_sorted_object_keys(payload),
            cleaned_text_type=type(cleaned_text).__name__,
        )
        raise CleaningError("Cleaned output `cleaned_text` must be a string")
    return cleaned_text.strip()


class TranscriptCleaner:
    def __init__(
        self,
        *,
        chat_client,
        diagnostic_context: dict[str, object] | None = None,
    ) -> None:
        self.chat_client = chat_client
        self.diagnostic_context = dict(diagnostic_context or {})

    @staticmethod
    def _split_header(draft: str) -> tuple[str, str]:
        """Split a 2C draft into (header block, transcript body)."""
        header, _, body = draft.partition("## Transcript")
        if not body:
            return "", draft.strip()
        return header.rstrip(), body.strip()

    def clean_with_summary(self, draft: str) -> tuple[str, str, str]:
        """Clean a draft and return (cleaned markdown, l2 summary, l3 brief)."""
        if not draft.strip():
            raise ValueError("empty draft")

        header, body = self._split_header(draft)
        source_lines = _timestamped_lines(body)
        request_log_context = _merge_log_context(
            self.diagnostic_context,
            has_timestamps=bool(source_lines),
            source_line_count=len(source_lines),
        )

        messages = [
            {"role": "system", "content": CLEANING_SYSTEM_PROMPT},
            {"role": "user", "content": body},
        ]

        retry_source_body = body if source_lines else None
        raw_output = self._call_with_retry(
            messages,
            request_log_context,
            source_body=retry_source_body,
        )

        response_log_context = _merge_log_context(
            request_log_context,
            response_length=len(raw_output),
            response_sample=_compact_log_text(raw_output),
        )
        payload = _load_cleaned_payload(raw_output, log_context=response_log_context)
        l2_summary = _extract_text_field(
            payload, "summary", log_context=response_log_context
        )
        l3_brief = _extract_text_field(
            payload, "brief", log_context=response_log_context
        )

        if source_lines:
            cleaned_body = _validate_timestamped_payload(
                body, payload, log_context=response_log_context
            )
        else:
            cleaned_body = _validate_plain_payload(
                payload, log_context=response_log_context
            )

        if header:
            cleaned_markdown = f"{header}\n\n{cleaned_body}\n"
        else:
            cleaned_markdown = f"{cleaned_body}\n"

        return cleaned_markdown, l2_summary, l3_brief

    def _call_with_retry(
        self,
        messages: list[dict],
        log_context: dict[str, object],
        *,
        source_body: str | None = None,
    ) -> str:
        """Call the model once; on a validation error retry once, then give up.

        Provider errors (ChatCompletionError) propagate immediately — those are
        not retryable here. Parse/shape errors (non-JSON, missing keys) and
        timestamp validation failures trigger the single retry, since big
        transcripts occasionally come back with a drifted format that a second
        call fixes.
        """
        last_raw = ""
        for attempt in (1, 2):
            try:
                last_raw = self.chat_client.complete(messages).strip()
            except ChatCompletionError:
                _log_clean_failure("clean_provider_failure", log_context=log_context)
                raise
            try:
                _assert_cleaned_payload(
                    last_raw,
                    source_body=source_body,
                    log_context=log_context,
                )
                return last_raw
            except CleaningError:
                if attempt == 2:
                    _log_clean_failure("clean_retry_exhausted", log_context=log_context)
                    raise
                continue
        return last_raw  # 不可达（两次循环必 return 或 raise）

    def clean(self, draft: str) -> str:
        """Clean a draft and return the full cleaned markdown document."""
        cleaned_markdown, _, _ = self.clean_with_summary(draft)
        return cleaned_markdown
