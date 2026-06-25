"""Utterance classification utilities for filtering trivial or question-like utterances."""

import re

# High-confidence question detector: must have question signal AND lack answer signal
_QUESTION_ENDINGS = ("?", "？", "呢", "嗎", "嘛")
_QUESTION_MARKERS = (
    "哪些",
    "什麼",
    "如何",
    "為什麼",
    "有沒有",
    "是否",
    "能否",
    "怎麼",
    "請問",
    "想問",
    "可不可以",
    "你有",
    "你會",
)
_ANSWER_MARKERS = (
    "我們會",
    "我們用",
    "我們有",
    "我會",
    "我有",
    "我遇到",
    "之前有",
    "當時",
    "有一次",
    "例如",
    "像是",
    "客戶要",
    "客戶說",
    "主管會",
    "同事幫",
    "遇到過",
    "處理方式",
    "解決方案",
    "解決了",
    "後來就",
    "因為所以",
    "結果是",
    "通常會",
    "其實是",
    "我做的是",
    "我的做法",
    "我負責",
)

# Filler patterns that should skip LLM evaluation
_FILLER_PATTERNS = frozenset(
    [
        "嗯",
        "嗯嗯",
        "好",
        "好的",
        "對",
        "對對",
        "是",
        "是的",
        "沒有",
        "沒",
        "嗯哼",
        "喔",
        "哦",
        "啊",
        "呃",
        "那個",
        "就是",
        "然後",
        "我想一下",
        "等一下",
        "讓我想想",
        "稍等",
        "ok",
        "okay",
        "yeah",
        "yes",
        "no",
        "hmm",
        "uh",
        "right",
        "sure",
        "got it",
        "i see",
        "mm",
    ]
)


def is_question_like(text: str) -> bool:
    """High-confidence question detector.

    Returns True only if the text has question markers AND lacks answer content markers.
    This avoids blocking real answers that happen to contain question words.

    Args:
        text: Utterance text to classify

    Returns:
        True if the text is question-like, False otherwise
    """
    stripped = text.strip()
    if not stripped:
        return False

    has_question_signal = stripped.endswith(_QUESTION_ENDINGS) or any(
        marker in stripped for marker in _QUESTION_MARKERS
    )
    if not has_question_signal:
        return False

    has_answer_content = any(marker in stripped for marker in _ANSWER_MARKERS)
    return not has_answer_content


def should_skip_utterance(text: str) -> bool:
    """Return True if utterance is too trivial to warrant LLM evaluation.

    Args:
        text: Utterance text to check

    Returns:
        True if the utterance should be skipped, False otherwise
    """
    stripped = text.strip()
    if len(stripped) < 5:
        return True
    normalized = stripped.lower().rstrip("。，.!?！？⋯…")
    if normalized in _FILLER_PATTERNS:
        return True
    if re.fullmatch(r"[\s\W]+", stripped):
        return True
    return False
