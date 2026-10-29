"""Chuẩn hóa văn bản tiếng Việt cho bộ phân loại ý định.

Tách riêng khỏi `intent_core.py` để có thể dùng ở nơi không cần scikit-learn
(ví dụ `intent_service` khi chỉ muốn chuẩn hóa câu).
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any


def normalize_text(text: Any) -> str:
    """
    Chuẩn hóa câu tiếng Việt: chữ thường, bỏ dấu (kể cả đ → d), bỏ ký tự đặc biệt,
    gộp khoảng trắng. Dùng chung cho train, predict và kiểm tra trùng lặp.
    """
    if text is None:
        return ""
    value = str(text).lower().replace("đ", "d")
    value = unicodedata.normalize("NFD", value)
    value = "".join(ch for ch in value if unicodedata.category(ch) != "Mn")
    value = re.sub(r"[^a-z0-9\s]", " ", value)
    return re.sub(r"\s+", " ", value).strip()
