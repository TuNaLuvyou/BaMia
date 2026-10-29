"""
Kiểm tra chất lượng dữ liệu trước khi huấn luyện.

Chạy:
    python -m chatbot.ml.validate_dataset \
        --data chatbot/ml/data/intents.csv \
        --golden chatbot/ml/data/golden.csv
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import pandas as pd

from chatbot.ml.console import ensure_utf8_stdout
from chatbot.ml.intent_core import (
    DEFAULT_DATA_PATH,
    DEFAULT_GOLDEN_PATH,
    MIN_SAMPLES_PER_LABEL,
    DatasetError,
    label_warnings,
    load_dataset,
    normalize_text,
)
from chatbot.ml.labels import LABELS


def validate(data_path: str | Path = DEFAULT_DATA_PATH,
             golden_path: str | Path | None = DEFAULT_GOLDEN_PATH) -> dict[str, Any]:
    """Trả về báo cáo kiểm tra dữ liệu (không raise nếu chỉ có cảnh báo)."""
    df = load_dataset(data_path)
    counts = {label: int(df["label"].value_counts().get(label, 0)) for label in LABELS}

    normalized = df["text"].map(normalize_text)
    duplicated_rows = int(normalized.duplicated(keep=False).sum())
    duplicated_unique = int(normalized[normalized.duplicated(keep=False)].nunique())

    conflicting: list[str] = []
    if duplicated_rows:
        grouped = df.assign(_norm=normalized).groupby("_norm")["label"].nunique()
        conflicting = sorted(grouped[grouped > 1].index.tolist())

    report: dict[str, Any] = {
        "data_path": str(data_path),
        "n_samples": int(len(df)),
        "label_counts": counts,
        "labels_below_minimum": [
            label for label, count in counts.items() if count < MIN_SAMPLES_PER_LABEL
        ],
        "minimum_required_per_label": MIN_SAMPLES_PER_LABEL,
        "duplicated_rows_after_normalization": duplicated_rows,
        "duplicated_unique_texts": duplicated_unique,
        "conflicting_duplicates": conflicting,
        "warnings": label_warnings(df),
        "leakage": [],
    }

    if golden_path:
        golden_df = load_dataset(golden_path, allow_empty=True)
        report["golden_path"] = str(golden_path)
        report["golden_samples"] = int(len(golden_df))
        if golden_df.empty:
            report["warnings"].append(
                "golden.csv đang rỗng — chưa thể đánh giá độc lập hay chạy retrain_intent."
            )
        else:
            train_texts = set(normalized)
            golden_norm = golden_df["text"].map(normalize_text)
            leaked = sorted(set(golden_norm) & train_texts)
            report["leakage"] = leaked
            if leaked:
                report["warnings"].append(
                    f"Có {len(leaked)} câu xuất hiện ở cả intents.csv và golden.csv (rò rỉ dữ liệu)."
                )
            golden_counts = {
                label: int(golden_df["label"].value_counts().get(label, 0)) for label in LABELS
            }
            report["golden_label_counts"] = golden_counts
            missing = [label for label, count in golden_counts.items() if count == 0]
            if missing:
                report["warnings"].append(
                    f"golden.csv chưa có mẫu cho nhãn: {', '.join(missing)}."
                )

    return report


def main(argv: list[str] | None = None) -> int:
    ensure_utf8_stdout()
    parser = argparse.ArgumentParser(description="Kiểm tra dữ liệu huấn luyện bộ phân loại ý định")
    parser.add_argument("--data", default=str(DEFAULT_DATA_PATH))
    parser.add_argument("--golden", default=str(DEFAULT_GOLDEN_PATH))
    parser.add_argument("--json", action="store_true", help="In báo cáo dạng JSON")
    args = parser.parse_args(argv)

    try:
        report = validate(args.data, args.golden)
    except DatasetError as exc:
        print(f"[LỖI] {exc}")
        return 2

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0

    print(f"Dữ liệu: {report['data_path']}")
    print(f"Tổng số mẫu: {report['n_samples']}")
    print("\nSố mẫu theo nhãn:")
    for label, count in report["label_counts"].items():
        flag = "  <-- CẦN BỔ SUNG" if count < MIN_SAMPLES_PER_LABEL else ""
        print(f"  {label:<20} {count:>4}{flag}")
    print(
        f"\nTrùng sau chuẩn hóa: {report['duplicated_unique_texts']} câu "
        f"({report['duplicated_rows_after_normalization']} dòng)"
    )
    if report.get("golden_path"):
        print(f"Golden: {report.get('golden_samples', 0)} câu")
    if report["leakage"]:
        print(f"Rò rỉ train/golden: {len(report['leakage'])} câu")
    print("\nCảnh báo:")
    if report["warnings"]:
        for warning in report["warnings"]:
            print(f"  - {warning}")
    else:
        print("  (không có)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
