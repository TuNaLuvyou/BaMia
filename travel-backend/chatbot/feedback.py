"""Thu thập dữ liệu phản hồi đã được admin duyệt (`corrected_label`) để huấn luyện lại."""

from __future__ import annotations

import csv
from pathlib import Path

from chatbot.ml.paths import ARTIFACTS_DIR
from chatbot.ml.text import normalize_text

DEFAULT_EXPORT_PATH = ARTIFACTS_DIR / "intent_feedback_export.csv"


def collect_corrected_rows() -> list[tuple[str, str]]:
    """
    Trả về [(text, corrected_label)] đã khử trùng theo câu chuẩn hóa.
    Chỉ lấy log có `corrected_label` — tức là con người đã duyệt.
    """
    from chatbot.models import IntentLog

    queryset = (
        IntentLog.objects.filter(corrected_label__isnull=False)
        .exclude(corrected_label="")
        .exclude(text="")
        .order_by("created_at")
        .values_list("text", "corrected_label")
    )

    seen: set[str] = set()
    rows: list[tuple[str, str]] = []
    for text, label in queryset:
        key = normalize_text(text)
        if not key or key in seen:
            continue
        seen.add(key)
        rows.append((str(text), str(label)))
    return rows


def write_feedback_csv(path: str | Path = DEFAULT_EXPORT_PATH) -> tuple[Path, int]:
    """Ghi CSV cùng định dạng `intents.csv` (text,label). Trả về (đường dẫn, số dòng)."""
    rows = collect_corrected_rows()
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["text", "label"])
        writer.writerows(rows)
    return path, len(rows)
