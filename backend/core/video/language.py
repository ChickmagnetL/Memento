"""ASR language routing (phase0: SenseVoice for zh, Moonshine for en)."""


def detect_asr_language(title: str, *, override: str = "auto", platform: str = "") -> str:
    """Pick the ASR language: explicit override, platform hint, else CJK-in-title heuristic."""
    if override in ("zh", "en"):
        return override
    # Bilibili videos are overwhelmingly Chinese.
    if platform == "bilibili":
        return "zh"
    has_cjk = any("一" <= char <= "鿿" for char in title)
    return "zh" if has_cjk else "en"
