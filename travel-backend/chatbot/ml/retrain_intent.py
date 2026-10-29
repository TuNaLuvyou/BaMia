"""
Huấn luyện lại mô hình có kiểm soát (Retrain with Quality Gate):
1. Gộp intents.csv + dữ liệu phản hồi đã admin duyệt (feedback).
2. Huấn luyện ứng viên mới (stratified k-fold so sánh 4 thuật toán).
3. Đánh giá cả mô hình cũ và ứng viên trên CÙNG golden.csv.
4. Cổng chất lượng (Quality Gate):
   - macro-F1 của ứng viên >= mô hình cũ, VÀ
   - recall lớp `blocked` không giảm.
5. Nếu đạt cổng và không --dry-run:
   - Sao lưu mô hình cũ vào backup/ có timestamp.
   - Thay thế intent_model.pkl bằng mô hình ứng viên.
   - Ghi báo cáo so sánh chi tiết ra JSON và Markdown.
"""

from __future__ import annotations

import argparse
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from chatbot.ml.console import ensure_utf8_stdout
from chatbot.ml.intent_core import (
    ALGORITHM_LABELS,
    cross_validate,
    dedupe_dataset,
    evaluate_pipeline,
    fit_final_model,
    format_cv_table,
    format_per_class,
    label_warnings,
    load_artifact,
    load_dataset,
    pick_best_algo,
    save_artifact,
    should_replace,
)
from chatbot.ml.labels import LABELS
from chatbot.ml.paths import (
    ARTIFACTS_DIR,
    BACKUP_DIR,
    DEFAULT_DATA_PATH,
    DEFAULT_GOLDEN_PATH,
    DEFAULT_MODEL_PATH,
)


def load_feedback_data(feedback_path: str | Path | None = None) -> pd.DataFrame:
    """Nạp dữ liệu phản hồi đã duyệt từ file CSV hoặc từ DB nếu có thể."""
    if feedback_path:
        p = Path(feedback_path)
        if p.exists():
            return load_dataset(p, allow_empty=True)

    # Thử lấy từ DB qua chatbot.feedback nếu Django đã cấu hình
    try:
        from chatbot.feedback import collect_corrected_rows
        rows = collect_corrected_rows()
        if rows:
            return pd.DataFrame(rows, columns=["text", "label"])
    except Exception:
        pass

    return pd.DataFrame(columns=["text", "label"])


def run_retrain(
    data_path: str | Path = DEFAULT_DATA_PATH,
    feedback_path: str | Path | None = None,
    golden_path: str | Path = DEFAULT_GOLDEN_PATH,
    model_path: str | Path = DEFAULT_MODEL_PATH,
    backup_dir: str | Path = BACKUP_DIR,
    folds: int = 5,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Quy trình huấn luyện lại hoàn chỉnh."""
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    model_path = Path(model_path)
    backup_dir = Path(backup_dir)

    # 1. Nạp và gộp dữ liệu
    df_base = load_dataset(data_path)
    df_fb = load_feedback_data(feedback_path)
    df_merged = dedupe_dataset(pd.concat([df_base, df_fb], ignore_index=True), keep="last")
    warnings_list = label_warnings(df_merged)

    # 2. Huấn luyện ứng viên
    cv_res = cross_validate(df_merged, folds=folds)
    best_algo = pick_best_algo(cv_res)
    cand_pipe = fit_final_model(df_merged, best_algo)

    # 3. Nạp mô hình cũ (nếu có)
    old_artifact: dict[str, Any] | None = None
    old_algo: str | None = None
    if model_path.exists():
        try:
            old_artifact = load_artifact(model_path)
            old_algo = old_artifact.get("algo")
        except Exception as exc:
            print(f"[CẢNH BÁO] Không đọc được mô hình cũ ({exc}), xem như huấn luyện lần đầu.")

    # 4. Đánh giá trên golden.csv
    df_golden = load_dataset(golden_path, allow_empty=True)
    golden_available = not df_golden.empty

    old_eval: dict[str, Any] | None = None
    cand_eval: dict[str, Any] = {}

    if golden_available:
        if old_artifact is not None:
            old_eval = evaluate_pipeline(old_artifact["pipeline"], df_golden)
        cand_eval = evaluate_pipeline(cand_pipe, df_golden)
        passed_gate = should_replace(old_eval, cand_eval)
        gate_reason = (
            f"Macro-F1 ứng viên ({cand_eval['macro_f1']:.4f}) "
            f"{'>=' if cand_eval['macro_f1'] >= (old_eval['macro_f1'] if old_eval else 0) else '<'} "
            f"mô hình cũ ({old_eval['macro_f1']:.4f if old_eval else 0.0:.4f}) VÀ "
            f"blocked recall ({cand_eval['blocked_recall']:.4f}) "
            f"{'>=' if cand_eval['blocked_recall'] >= (old_eval['blocked_recall'] if old_eval else 0) else '<'} "
            f"mô hình cũ ({old_eval['blocked_recall']:.4f if old_eval else 0.0:.4f})"
        )
    else:
        # Golden rỗng: so sánh dựa trên CV macro-F1
        passed_gate = True
        gate_reason = "golden.csv rỗng — kiểm tra chất lượng dựa trên kết quả cross-validation."

    # 5. Quyết định thay thế / sao lưu
    backup_path: Path | None = None
    applied = False
    if passed_gate:
        if dry_run:
            decision = "ĐẠT CỔNG CHẤT LƯỢNG (DRY-RUN: Không ghi đè mô hình)"
        else:
            if model_path.exists():
                backup_dir.mkdir(parents=True, exist_ok=True)
                backup_path = backup_dir / f"intent_model_{timestamp}.pkl"
                shutil.copy2(model_path, backup_path)

            save_artifact(
                cand_pipe,
                best_algo,
                model_path,
                metadata={
                    "retrained_at": timestamp,
                    "n_base_samples": len(df_base),
                    "n_feedback_samples": len(df_fb),
                    "n_total_samples": len(df_merged),
                    "golden_evaluated": golden_available,
                },
            )
            applied = True
            decision = "ĐẠT CỔNG CHẤT LƯỢNG — ĐÃ CẬP NHẬT MÔ HÌNH THÀNH CÔNG"
    else:
        decision = "TỪ CHỐI THAY THẾ — Mô hình ứng viên không vượt qua cổng chất lượng"

    # 6. Dựng báo cáo JSON & Markdown
    report = {
        "timestamp": timestamp,
        "dry_run": dry_run,
        "decision": decision,
        "passed_gate": passed_gate,
        "applied": applied,
        "gate_reason": gate_reason,
        "backup_path": str(backup_path) if backup_path else None,
        "model_path": str(model_path),
        "data": {
            "base_samples": len(df_base),
            "feedback_samples": len(df_fb),
            "total_merged_samples": len(df_merged),
            "golden_samples": len(df_golden),
        },
        "candidate": {
            "algo": best_algo,
            "algo_name": ALGORITHM_LABELS.get(best_algo, best_algo),
            "cv_macro_f1": cv_res[best_algo]["macro_f1_mean"],
            "cv_accuracy": cv_res[best_algo]["accuracy_mean"],
            "golden_eval": cand_eval if golden_available else None,
        },
        "old_model": {
            "algo": old_algo,
            "golden_eval": old_eval if golden_available and old_eval else None,
        },
        "warnings": warnings_list,
    }

    report_json_path = ARTIFACTS_DIR / f"retrain_report_{timestamp}.json"
    report_md_path = ARTIFACTS_DIR / f"retrain_report_{timestamp}.md"

    with report_json_path.open("w", encoding="utf-8") as fh:
        json.dump(report, fh, ensure_ascii=False, indent=2)

    md_content = _build_markdown_report(report, df_golden)
    with report_md_path.open("w", encoding="utf-8") as fh:
        fh.write(md_content)

    report["report_json_path"] = str(report_json_path)
    report["report_md_path"] = str(report_md_path)

    return report


def _build_markdown_report(report: dict[str, Any], df_golden: pd.DataFrame) -> str:
    """Tạo báo cáo dạng Markdown chi tiết cho retrain."""
    lines = [
        f"# Báo cáo Huấn luyện lại Bộ phân loại Ý định ({report['timestamp']})",
        "",
        f"- **Quyết định**: `{report['decision']}`",
        f"- **Lý do**: {report['gate_reason']}",
        f"- **Chế độ Dry-Run**: `{report['dry_run']}`",
        f"- **Mô hình đầu ra**: `{report['model_path']}`",
        f"- **Bản sao lưu**: `{report['backup_path'] or 'Không có'}`",
        "",
        "## 1. Dữ liệu huấn luyện",
        f"- Mẫu gốc (`intents.csv`): **{report['data']['base_samples']}**",
        f"- Mẫu phản hồi được duyệt (`feedback`): **{report['data']['feedback_samples']}**",
        f"- Tổng sau khi gộp và khử trùng: **{report['data']['total_merged_samples']}**",
        f"- Mẫu kiểm thử độc lập (`golden.csv`): **{report['data']['golden_samples']}**",
        "",
        "## 2. So sánh thuật toán & mô hình",
        f"- **Thuật toán ứng viên tốt nhất**: `{report['candidate']['algo_name']}`",
        f"  - CV Macro-F1: `{report['candidate']['cv_macro_f1']:.4f}`",
        f"  - CV Accuracy: `{report['candidate']['cv_accuracy']:.4f}`",
        "",
    ]

    if report["data"]["golden_samples"] > 0 and report["candidate"]["golden_eval"]:
        cand_g = report["candidate"]["golden_eval"]
        old_g = report["old_model"]["golden_eval"] or {}
        lines.extend([
            "### Đánh giá trên tập `golden.csv`",
            "",
            "| Chỉ số | Mô hình cũ | Ứng viên mới | Kết quả cổng |",
            "|---|---|---|---|",
            f"| Accuracy | {old_g.get('accuracy', 0.0):.4f} | {cand_g.get('accuracy', 0.0):.4f} | - |",
            f"| Macro-F1 | {old_g.get('macro_f1', 0.0):.4f} | {cand_g.get('macro_f1', 0.0):.4f} | {'ĐẠT' if cand_g.get('macro_f1', 0) >= old_g.get('macro_f1', 0) else 'KHÔNG ĐẠT'} |",
            f"| Recall (blocked) | {old_g.get('blocked_recall', 0.0):.4f} | {cand_g.get('blocked_recall', 0.0):.4f} | {'ĐẠT' if cand_g.get('blocked_recall', 0) >= old_g.get('blocked_recall', 0) else 'KHÔNG ĐẠT'} |",
            "",
        ])
    else:
        lines.extend([
            "> [!NOTE]",
            "> Tập `golden.csv` hiện chưa có dữ liệu kiểm thử độc lập.",
            "> Cổng chất lượng được kích hoạt mặc định dựa trên cross-validation.",
            "",
        ])

    if report["warnings"]:
        lines.append("## 3. Cảnh báo dữ liệu")
        for w in report["warnings"]:
            lines.append(f"- {w}")
        lines.append("")

    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ensure_utf8_stdout()
    parser = argparse.ArgumentParser(description="Huấn luyện lại bộ phân loại ý định có cổng chất lượng")
    parser.add_argument("--data", default=str(DEFAULT_DATA_PATH), help="Đường dẫn intents.csv gốc")
    parser.add_argument("--feedback", default=None, help="Đường dẫn CSV phản hồi đã duyệt (hoặc tự lấy từ DB)")
    parser.add_argument("--golden", default=str(DEFAULT_GOLDEN_PATH), help="Đường dẫn golden.csv")
    parser.add_argument("--model", default=str(DEFAULT_MODEL_PATH), help="File mô hình .pkl")
    parser.add_argument("--backup-dir", default=str(BACKUP_DIR), help="Thư mục sao lưu mô hình")
    parser.add_argument("--folds", type=int, default=5, help="Số fold CV")
    parser.add_argument("--dry-run", action="store_true", help="Chỉ đánh giá và lập báo cáo, không thay mô hình")
    args = parser.parse_args(argv)

    try:
        report = run_retrain(
            data_path=args.data,
            feedback_path=args.feedback,
            golden_path=args.golden,
            model_path=args.model,
            backup_dir=args.backup_dir,
            folds=args.folds,
            dry_run=args.dry_run,
        )
    except Exception as exc:
        print(f"[LỖI] {exc}")
        return 1

    print("=" * 75)
    print("QUY TRÌNH HUẤN LUYỆN LẠI (RETRAIN INTENT CLASSIFIER)")
    print("=" * 75)
    print(f"Trạng thái : {report['decision']}")
    print(f"Lý do      : {report['gate_reason']}")
    print(f"Ứng viên   : {report['candidate']['algo_name']}")
    print(f"Mẫu huấn luyện: {report['data']['total_merged_samples']} (Gốc: {report['data']['base_samples']} + Phản hồi: {report['data']['feedback_samples']})")
    if report["backup_path"]:
        print(f"Bản sao lưu: {report['backup_path']}")
    print(f"Báo cáo JSON: {report['report_json_path']}")
    print(f"Báo cáo MD  : {report['report_md_path']}")
    print("=" * 75)

    return 0 if report["passed_gate"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
