"""
CLI huấn luyện bộ phân loại ý định (dùng chung cho management command).

Chạy trực tiếp không cần Django:
    python -m chatbot.ml.train_intent \
        --data chatbot/ml/data/intents.csv \
        --golden chatbot/ml/data/golden.csv
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from chatbot.ml.console import ensure_utf8_stdout
from chatbot.ml.intent_core import (
    DatasetError,
    format_confusion,
    format_cv_table,
    format_per_class,
    train_model,
)
from chatbot.ml.paths import (
    DEFAULT_DATA_PATH,
    DEFAULT_GOLDEN_PATH,
    DEFAULT_MODEL_PATH,
    DEFAULT_REPORT_PATH,
)


def run_training(
    data_path: str | Path = DEFAULT_DATA_PATH,
    golden_path: str | Path | None = DEFAULT_GOLDEN_PATH,
    model_path: str | Path = DEFAULT_MODEL_PATH,
    report_path: str | Path = DEFAULT_REPORT_PATH,
    folds: int = 5,
) -> tuple[dict[str, Any], list[str]]:
    """Huấn luyện + trả về (report, các dòng log để in)."""
    result = train_model(
        data_path=data_path,
        golden_path=golden_path,
        model_path=model_path,
        report_path=report_path,
        folds=folds,
    )
    report = result["report"]

    lines: list[str] = []
    lines.append(f"Dữ liệu: {report['data_path']} ({report['n_samples']} mẫu)")
    lines.append("")
    lines.append("=== So sánh 4 thuật toán (stratified k-fold) ===")
    lines.append(format_cv_table({**report["cv"], "_meta": report["cv_meta"]}))
    lines.append("")
    lines.append(f"Thuật toán được chọn: {report['best_algo_name']} ({report['best_algo']})")
    lines.append("")
    lines.append("=== Báo cáo từng lớp (dự đoán out-of-fold của mô hình tốt nhất) ===")
    lines.append(format_per_class(report["best_oof_per_class"]))
    lines.append("")
    lines.append("=== Confusion matrix (hàng = nhãn thật, cột = dự đoán) ===")
    lines.append(format_confusion(report["best_oof_confusion_matrix"]))
    lines.append("")

    golden = report.get("golden") or {}
    if golden.get("n_samples", 0) > 0:
        lines.append(
            f"=== Đánh giá trên golden.csv ({golden['n_samples']} câu) ===\n"
            f"Accuracy: {golden['accuracy']:.4f} | Macro-F1: {golden['macro_f1']:.4f}"
        )
        lines.append(format_per_class(golden["per_class"]))
        lines.append("")
    else:
        lines.append(
            "=== golden.csv chưa có dữ liệu ===\n"
            "Chưa có đánh giá độc lập. Hãy viết golden.csv bằng tay (xem chatbot/ml/data/README.md)."
        )
        lines.append("")

    if report["warnings"]:
        lines.append("=== CẢNH BÁO DỮ LIỆU ===")
        lines.extend(f"  - {warning}" for warning in report["warnings"])
        lines.append("")

    lines.append(f"Đã lưu mô hình: {report['model_path']}")
    lines.append(f"Đã lưu báo cáo: {report_path}")
    return report, lines


def main(argv: list[str] | None = None) -> int:
    ensure_utf8_stdout()
    parser = argparse.ArgumentParser(description="Huấn luyện bộ phân loại ý định chatbot")
    parser.add_argument("--data", default=str(DEFAULT_DATA_PATH))
    parser.add_argument("--golden", default=str(DEFAULT_GOLDEN_PATH))
    parser.add_argument("--output", default=str(DEFAULT_MODEL_PATH))
    parser.add_argument("--report", default=str(DEFAULT_REPORT_PATH))
    parser.add_argument("--folds", type=int, default=5)
    args = parser.parse_args(argv)

    try:
        _, lines = run_training(
            data_path=args.data,
            golden_path=args.golden,
            model_path=args.output,
            report_path=args.report,
            folds=args.folds,
        )
    except DatasetError as exc:
        print(f"[LỖI] {exc}")
        return 2
    except FileNotFoundError as exc:
        print(f"[LỖI] {exc}")
        return 2

    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
    raise SystemExit(main())
