"""Chinese-aware tokenization for BM25 (jieba based)."""

import jieba


def tokenize(text: str) -> list[str]:
    """Tokenize text for BM25: jieba search-mode cut, drop non-word tokens."""
    return [token for token in jieba.cut_for_search(text) if token.strip() and any(ch.isalnum() for ch in token)]
