"""
Đánh giá đường cơ sở (Baseline) — cài lại logic LUẬT CŨ thành bộ phân loại
và so sánh với mô hình học máy trên cùng tập dữ liệu (golden.csv).

Luật cũ:
  1. security_keywords -> blocked
  2. regex needsRefresh -> account_status
  3. từ khóa hỗ trợ/escalate -> complaint_support
  4. còn lại -> unknown (không bao quát được tour_search, destination_info, chitchat)
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

import pandas as pd
from sklearn.metrics import accuracy_score, classification_report, f1_score, recall_score

from chatbot.ml.console import ensure_utf8_stdout
from chatbot.ml.intent_core import (
    evaluate_pipeline,
    format_per_class,
    load_artifact,
    load_dataset,
)
from chatbot.ml.labels import LABELS
from chatbot.ml.paths import (
    DEFAULT_BASELINE_REPORT_PATH,
    DEFAULT_GOLDEN_PATH,
    DEFAULT_MODEL_PATH,
)

# Từ khóa bảo mật cũ (views.py)
SECURITY_KEYWORDS = [
    "database", "password", "mật khẩu", "cấu trúc sql",
    "select *", "delete from", "drop table", "backend code",
]

# Regex làm mới giỏ hàng/booking cũ (Chatbot.jsx:153)
REFRESH_REGEX = re.compile(r"giỏ hàng|đơn hàng|booking|kiểm tra|cập nhật", re.IGNORECASE)

# Từ khóa hỗ trợ / khiếu nại (Chatbot.jsx & views.py ESCALATE)
COMPLAINT_KEYWORDS = [
    "khiếu nại", "phàn nàn", "nhân viên", "tổng đài", "hotline",
    "hỗ trợ", "tư vấn viên", "gặp người", "hoàn tiền", "bồi thường",
    "sự cố", "thất vọng", "gặp nhân viên", "chăm sóc khách hàng",
]


def classify_rule_baseline(text: str) -> str:
    """
    Bộ phân loại luật cứng cũ:
    - security_keywords -> blocked
    - regex needsRefresh -> account_status
    - từ khóa hỗ trợ/khiếu nại -> complaint_support
    - còn lại -> unknown (luật cũ không có cách phân biệt tour_search, destination_info, chitchat)
    """
    lower = text.lower()
    for kw in SECURITY_KEYWORDS:
        if kw in lower:
            return "blocked"
    if REFRESH_REGEX.search(lower):
        return "account_status"
    for kw in COMPLAINT_KEYWORDS:
        if kw in lower:
            return "complaint_support"
    return "unknown"


def evaluate_baseline(df: pd.DataFrame) -> dict[str, Any]:
    """Đánh giá bộ phân loại luật cũ trên tập df có cột text, label."""
    if df.empty:
        return {"n_samples": 0}

    y_true = df["label"].astype(str).tolist()
    y_pred = [classify_rule_baseline(t) for t in df["text"]]

    # Phân loại báo cáo theo danh sách 6 nhãn chính thức
    labels_list = list(LABELS)
    report = classification_report(
        y_true, y_pred, labels=labels_list, output_dict=True, zero_division=0
    )

    per_class = {
        lbl: {
            "precision": float(report[lbl]["precision"]),
            "recall": float(report[lbl]["recall"]),
            "f1": float(report[lbl]["f1-score"]),
            "support": int(report[lbl]["support"]),
        }
        for lbl in labels_list
    }

    acc = float(accuracy_score(y_true, y_pred))
    macro_f1 = float(f1_score(y_true, y_pred, labels=labels_list, average="macro", zero_division=0))
    blocked_rec = float(
        recall_score(y_true, y_pred, labels=["blocked"], average="macro", zero_division=0)
    )

    unknown_count = sum(1 for p in y_pred if p == "unknown")

    return {
        "n_samples": len(df),
        "accuracy": acc,
        "macro_f1": macro_f1,
        "blocked_recall": blocked_rec,
        "unknown_count": unknown_count,
        "unknown_rate": unknown_count / len(df) if len(df) else 0.0,
        "per_class": per_class,
    }


def format_comparison_table(
    baseline_metrics: dict[str, Any], ml_metrics: dict[str, Any]
) -> str:
    """Tạo bảng so sánh đẹp giữa Baseline (Luật cũ) và ML (Học máy)."""
    lines = []
    header = f"{'Chỉ số / Nhãn':<22} | {'Baseline (Luật cũ)':<20} | {'Mô hình ML (Mới)':<20} | {'Chênh lệch (ML - Base)':<22}"
    lines.append(header)
    lines.append("-" * len(header))

    def diff_str(val_ml, val_base):
        diff = val_ml - val_base
        sign = "+" if diff >= 0 else ""
        return f"{sign}{diff:.4f}"

    lines.append(
        f"{'Accuracy':<22} | {baseline_metrics.get('accuracy', 0.0):<20.4f} | "
        f"{ml_metrics.get('accuracy', 0.0):<20.4f} | "
        f"{diff_str(ml_metrics.get('accuracy', 0.0), baseline_metrics.get('accuracy', 0.0)):<22}"
    )
    lines.append(
        f"{'Macro-F1':<22} | {baseline_metrics.get('macro_f1', 0.0):<20.4f} | "
        f"{ml_metrics.get('macro_f1', 0.0):<20.4f} | "
        f"{diff_str(ml_metrics.get('macro_f1', 0.0), baseline_metrics.get('macro_f1', 0.0)):<22}"
    )
    lines.append(
        f"{'Recall (blocked)':<22} | {baseline_metrics.get('blocked_recall', 0.0):<20.4f} | "
        f"{ml_metrics.get('blocked_recall', 0.0):<20.4f} | "
        f"{diff_str(ml_metrics.get('blocked_recall', 0.0), baseline_metrics.get('blocked_recall', 0.0)):<22}"
    )
    lines.append("-" * len(header))
    lines.append("Chi tiết F1-score từng lớp:")

    base_pc = baseline_metrics.get("per_class", {})
    ml_pc = ml_metrics.get("per_class", {})
    for lbl in LABELS:
        f1_b = base_pc.get(lbl, {}).get("f1", 0.0)
        f1_m = ml_pc.get(lbl, {}).get("f1", 0.0)
        lines.append(
            f"  {lbl:<20} | {f1_b:<20.4f} | {f1_m:<20.4f} | {diff_str(f1_m, f1_b):<22}"
        )

    return "\n".join(lines)


def run_evaluation(
    golden_path: str | Path = DEFAULT_GOLDEN_PATH,
    model_path: str | Path = DEFAULT_MODEL_PATH,
    output_path: str | Path | None = DEFAULT_BASELINE_REPORT_PATH,
) -> dict[str, Any]:
    """Chạy đánh giá baseline và ML trên cùng tập dữ liệu."""
    df_golden = load_dataset(golden_path, allow_empty=True)
    if df_golden.empty:
        print(f"[CẢNH BÁO] Tập {golden_path} đang rỗng hoặc chưa có dữ liệu.")
        print("Cần viết golden.csv thủ công để có số liệu kiểm thử độc lập cho báo cáo.")
        return {"golden_samples": 0}

    base_metrics = evaluate_baseline(df_golden)

    ml_metrics: dict[str, Any] = {}
    algo_name = "N/A"
    try:
        artifact = load_artifact(model_path)
        algo_name = artifact.get("algo", "ML")
        ml_metrics = evaluate_pipeline(artifact["pipeline"], df_golden)
    except Exception as exc:
        print(f"[CẢNH BÁO] Không tải được mô hình ML ({model_path}): {exc}")

    report = {
        "golden_path": str(golden_path),
        "golden_samples": len(df_golden),
        "model_path": str(model_path),
        "ml_algo": algo_name,
        "baseline": base_metrics,
        "ml": ml_metrics,
    }

    if output_path:
        out_p = Path(output_path)
        out_p.parent.mkdir(parents=True, exist_ok=True)
        with out_p.open("w", encoding="utf-8") as fh:
            json.dump(report, fh, ensure_ascii=False, indent=2)

    return report


def main(argv: list[str] | None = None) -> int:
    ensure_utf8_stdout()
    parser = argparse.ArgumentParser(description="Đánh giá đường cơ sở (luật cũ) so với mô hình ML")
    parser.add_argument("--golden", default=str(DEFAULT_GOLDEN_PATH), help="Đường dẫn file golden.csv")
    parser.add_argument("--model", default=str(DEFAULT_MODEL_PATH), help="Đường dẫn mô hình ML (.pkl)")
    parser.add_argument("--output", default=str(DEFAULT_BASELINE_REPORT_PATH), help="File JSON lưu báo cáo")
    args = parser.parse_args(argv)

    report = run_evaluation(args.golden, args.model, args.output)
    if report.get("golden_samples", 0) == 0:
        return 0

    print("=" * 80)
    print(f"ĐÁNH GIÁ ĐƯỜNG CƠ SỞ (BASELINE SO VỚI MÔ HÌNH HỌC MÁY)")
    print(f"Tập kiểm thử: {report['golden_path']} ({report['golden_samples']} mẫu)")
    print("=" * 80)
    print("")

    if report.get("ml"):
        print(format_comparison_table(report["baseline"], report["ml"]))
    else:
        print("Chi tiết Baseline (Luật cũ):")
        print(format_per_class(report["baseline"]["per_class"]))

    print("")
    print(f"Tỉ lệ câu luật cũ không xử lý được (unknown): "
          f"{report['baseline']['unknown_count']}/{report['golden_samples']} "
          f"({report['baseline']['unknown_rate'] * 100:.1f}%)")

    if args.output:
        print(f"Báo cáo chi tiết đã lưu: {args.output}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
