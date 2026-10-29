"""
Lõi huấn luyện / đánh giá bộ phân loại ý định.

Thiết kế:
- Đặc trưng: TF-IDF theo n-gram **ký tự** (char_wb, 2..5) — phù hợp tiếng Việt có dấu,
  không cần từ điển/tách từ, chịu được lỗi gõ và biến thể không dấu.
- So sánh 4 thuật toán bằng stratified k-fold: MultinomialNB, kNN, SVM (linear),
  Decision Tree. Chọn theo macro-F1 trung bình.
- Mọi số liệu đều sinh ra từ dữ liệu thật tại thời điểm chạy; không hard-code kết quả.

Module này không phụ thuộc Django để có thể chạy trực tiếp:
    python -m chatbot.ml.train_intent --data chatbot/ml/data/intents.csv
"""

from __future__ import annotations

import json
import pickle
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
    recall_score,
)
from sklearn.model_selection import StratifiedKFold, cross_val_predict
from sklearn.naive_bayes import MultinomialNB
from sklearn.neighbors import KNeighborsClassifier
from sklearn.pipeline import Pipeline
from sklearn.svm import SVC
from sklearn.tree import DecisionTreeClassifier

from chatbot.ml.labels import DEFAULT_THRESHOLDS, LABELS
from chatbot.ml.paths import (
    DEFAULT_DATA_PATH,
    DEFAULT_GOLDEN_PATH,
    DEFAULT_MODEL_PATH,
    DEFAULT_REPORT_PATH,
)
from chatbot.ml.text import normalize_text

__all__ = [
    "ALGORITHMS",
    "ALGORITHM_LABELS",
    "DatasetError",
    "build_pipeline",
    "cross_validate",
    "cross_val_predictions",
    "dedupe_dataset",
    "evaluate_pipeline",
    "fit_final_model",
    "format_confusion",
    "format_cv_table",
    "format_per_class",
    "label_warnings",
    "load_artifact",
    "load_dataset",
    "normalize_text",
    "pick_best_algo",
    "save_artifact",
    "should_replace",
    "train_model",
]

ALGORITHMS = ("naive_bayes", "knn", "svm", "decision_tree")
ALGORITHM_LABELS = {
    "naive_bayes": "Multinomial Naive Bayes",
    "knn": "k-Nearest Neighbors",
    "svm": "SVM (linear)",
    "decision_tree": "Decision Tree",
}

MIN_SAMPLES_PER_LABEL = 100


class DatasetError(ValueError):
    """Dữ liệu huấn luyện không hợp lệ."""


# ---------------------------------------------------------------------------
# Dữ liệu
# ---------------------------------------------------------------------------

def load_dataset(path: str | Path, *, allow_empty: bool = False) -> pd.DataFrame:
    """Đọc CSV 2 cột `text,label`, chuẩn hóa, kiểm tra nhãn hợp lệ."""
    path = Path(path)
    if not path.exists():
        raise DatasetError(f"Không tìm thấy file dữ liệu: {path}")

    try:
        df = pd.read_csv(path, dtype=str, keep_default_na=False, encoding="utf-8-sig")
    except pd.errors.EmptyDataError:
        df = pd.DataFrame(columns=["text", "label"])

    missing = {"text", "label"} - set(df.columns)
    if missing:
        raise DatasetError(f"{path} thiếu cột: {', '.join(sorted(missing))}")

    df = df[["text", "label"]].copy()
    df["text"] = df["text"].astype(str).str.strip()
    df["label"] = df["label"].astype(str).str.strip()
    df = df[(df["text"] != "") & (df["label"] != "")].reset_index(drop=True)

    if df.empty:
        if allow_empty:
            return df
        raise DatasetError(f"{path} không có dòng dữ liệu hợp lệ.")

    invalid = sorted(set(df["label"]) - set(LABELS))
    if invalid:
        raise DatasetError(
            f"{path} có nhãn không hợp lệ: {invalid}. Nhãn hợp lệ: {list(LABELS)}"
        )
    return df


def label_warnings(df: pd.DataFrame) -> list[str]:
    """Cảnh báo dữ liệu chưa đủ lớn / trùng lặp / xung đột nhãn."""
    result: list[str] = []
    counts = df["label"].value_counts()
    for label in LABELS:
        count = int(counts.get(label, 0))
        if count < MIN_SAMPLES_PER_LABEL:
            result.append(
                f"Nhãn '{label}' chỉ có {count} mẫu (<{MIN_SAMPLES_PER_LABEL}). "
                "Kết quả chỉ mang tính chạy thử, KHÔNG dùng để báo cáo là số liệu thật."
            )

    normalized = df["text"].map(normalize_text)
    duplicated = normalized[normalized.duplicated(keep=False)]
    if not duplicated.empty:
        conflict = (
            df.assign(_norm=normalized)
            .groupby("_norm")["label"]
            .nunique()
        )
        conflicting = conflict[conflict > 1]
        result.append(
            f"Có {duplicated.nunique()} câu trùng sau chuẩn hóa"
            + (
                f", trong đó {len(conflicting)} câu gắn nhiều nhãn khác nhau."
                if len(conflicting)
                else "."
            )
        )
    return result


def dedupe_dataset(df: pd.DataFrame, *, keep: str = "last") -> pd.DataFrame:
    """Gộp trùng theo câu đã chuẩn hóa (mặc định giữ bản ghi sau = bản người duyệt)."""
    work = df.copy()
    work["_norm"] = work["text"].map(normalize_text)
    work = work[work["_norm"] != ""]
    work = work.drop_duplicates(subset="_norm", keep=keep)
    return work.drop(columns=["_norm"]).reset_index(drop=True)


# ---------------------------------------------------------------------------
# Mô hình
# ---------------------------------------------------------------------------

def build_pipeline(algo: str) -> Pipeline:
    """Tạo pipeline TF-IDF ký tự + thuật toán phân loại."""
    if algo not in ALGORITHMS:
        raise ValueError(f"Thuật toán không hỗ trợ: {algo}. Chọn trong {ALGORITHMS}")

    vectorizer = TfidfVectorizer(
        analyzer="char_wb",
        ngram_range=(2, 5),
        sublinear_tf=True,
        min_df=1,
        lowercase=False,  # normalize_text đã lo phần chữ thường/bỏ dấu
    )

    if algo == "naive_bayes":
        classifier = MultinomialNB(alpha=0.3)
    elif algo == "knn":
        classifier = KNeighborsClassifier(n_neighbors=5, metric="cosine", weights="distance")
    elif algo == "svm":
        # SVC(probability=True) đã bị deprecate từ scikit-learn 1.9; bọc calibration
        # để vẫn có predict_proba (cần cho ngưỡng tin cậy theo nhãn).
        classifier = CalibratedClassifierCV(
            SVC(kernel="linear", C=1.0, random_state=42), method="sigmoid", cv=3
        )
    else:
        classifier = DecisionTreeClassifier(random_state=42)

    return Pipeline([("tfidf", vectorizer), ("clf", classifier)])


def _make_splits(y: Iterable[str], folds: int) -> tuple[StratifiedKFold, int]:
    counts = pd.Series(list(y)).value_counts()
    min_count = int(counts.min()) if not counts.empty else 0
    usable = min(folds, min_count)
    if usable < 2:
        raise DatasetError(
            "Không đủ mẫu mỗi nhãn để chạy stratified k-fold "
            f"(nhãn ít nhất có {min_count} mẫu). Cần tối thiểu 2 mẫu/nhãn."
        )
    return StratifiedKFold(n_splits=usable, shuffle=True, random_state=42), usable


def _fold_metrics(y_true, y_pred) -> dict[str, float]:
    return {
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "macro_f1": float(f1_score(y_true, y_pred, average="macro", zero_division=0)),
        "blocked_recall": float(
            recall_score(y_true, y_pred, labels=["blocked"], average="macro", zero_division=0)
        ),
    }


def cross_validate(df: pd.DataFrame, folds: int = 5) -> dict[str, Any]:
    """Stratified k-fold cho cả 4 thuật toán trên cùng tập dữ liệu."""
    texts = df["text"].map(normalize_text).to_numpy()
    labels = df["label"].to_numpy()
    splitter, usable_folds = _make_splits(labels, folds)

    results: dict[str, Any] = {}
    for algo in ALGORITHMS:
        fold_rows = []
        for train_idx, test_idx in splitter.split(texts, labels):
            pipe = build_pipeline(algo)
            pipe.fit(texts[train_idx], labels[train_idx])
            fold_rows.append(_fold_metrics(labels[test_idx], pipe.predict(texts[test_idx])))

        results[algo] = {
            "name": ALGORITHM_LABELS[algo],
            "folds": fold_rows,
            "accuracy_mean": float(np.mean([r["accuracy"] for r in fold_rows])),
            "accuracy_std": float(np.std([r["accuracy"] for r in fold_rows])),
            "macro_f1_mean": float(np.mean([r["macro_f1"] for r in fold_rows])),
            "macro_f1_std": float(np.std([r["macro_f1"] for r in fold_rows])),
            "blocked_recall_mean": float(np.mean([r["blocked_recall"] for r in fold_rows])),
            "blocked_recall_std": float(np.std([r["blocked_recall"] for r in fold_rows])),
        }

    results["_meta"] = {
        "folds": usable_folds,
        "requested_folds": folds,
        "n_samples": int(len(df)),
    }
    return results


def evaluate_pipeline(pipe: Pipeline, df: pd.DataFrame) -> dict[str, Any]:
    """Đánh giá pipeline đã fit trên một tập có nhãn (dùng cho golden / retrain gate)."""
    if df.empty:
        return {"n_samples": 0}

    texts = df["text"].map(normalize_text).to_numpy()
    labels = df["label"].to_numpy()
    predicted = pipe.predict(texts)

    report = classification_report(
        labels, predicted, labels=list(LABELS), output_dict=True, zero_division=0
    )
    return {
        "n_samples": int(len(df)),
        "accuracy": float(accuracy_score(labels, predicted)),
        "macro_f1": float(f1_score(labels, predicted, average="macro", zero_division=0)),
        "weighted_f1": float(f1_score(labels, predicted, average="weighted", zero_division=0)),
        "blocked_recall": float(
            recall_score(labels, predicted, labels=["blocked"], average="macro", zero_division=0)
        ),
        "per_class": {
            label: {
                "precision": float(report[label]["precision"]),
                "recall": float(report[label]["recall"]),
                "f1": float(report[label]["f1-score"]),
                "support": int(report[label]["support"]),
            }
            for label in LABELS
        },
        "confusion_matrix": confusion_matrix(
            labels, predicted, labels=list(LABELS)
        ).tolist(),
        "labels_order": list(LABELS),
    }


def cross_val_predictions(df: pd.DataFrame, algo: str, folds: int = 5) -> dict[str, Any]:
    """Dự đoán out-of-fold để lấy báo cáo từng lớp + confusion matrix của thuật toán tốt nhất."""
    texts = df["text"].map(normalize_text).to_numpy()
    labels = df["label"].to_numpy()
    splitter, _ = _make_splits(labels, folds)
    predicted = cross_val_predict(
        build_pipeline(algo), texts, labels, cv=splitter, method="predict"
    )
    report = classification_report(
        labels, predicted, labels=list(LABELS), output_dict=True, zero_division=0
    )
    return {
        "per_class": {
            label: {
                "precision": float(report[label]["precision"]),
                "recall": float(report[label]["recall"]),
                "f1": float(report[label]["f1-score"]),
                "support": int(report[label]["support"]),
            }
            for label in LABELS
        },
        "confusion_matrix": confusion_matrix(labels, predicted, labels=list(LABELS)).tolist(),
        "labels_order": list(LABELS),
        "accuracy": float(accuracy_score(labels, predicted)),
        "macro_f1": float(f1_score(labels, predicted, average="macro", zero_division=0)),
    }


def pick_best_algo(cv_results: dict[str, Any]) -> str:
    """Chọn thuật toán theo macro-F1 trung bình, hoà thì ưu tiên accuracy."""
    candidates = [algo for algo in ALGORITHMS if algo in cv_results]
    return max(
        candidates,
        key=lambda a: (cv_results[a]["macro_f1_mean"], cv_results[a]["accuracy_mean"]),
    )


def fit_final_model(df: pd.DataFrame, algo: str) -> Pipeline:
    texts = df["text"].map(normalize_text).to_numpy()
    labels = df["label"].to_numpy()
    pipe = build_pipeline(algo)
    pipe.fit(texts, labels)
    return pipe


def save_artifact(
    pipe: Pipeline,
    algo: str,
    path: str | Path = DEFAULT_MODEL_PATH,
    *,
    metadata: dict[str, Any] | None = None,
    thresholds: dict[str, float] | None = None,
) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "format_version": 1,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "algo": algo,
        "labels": list(LABELS),
        "thresholds": dict(thresholds or DEFAULT_THRESHOLDS),
        "pipeline": pipe,
        "metadata": metadata or {},
    }
    with path.open("wb") as fh:
        pickle.dump(payload, fh)
    return path


def load_artifact(path: str | Path = DEFAULT_MODEL_PATH) -> dict[str, Any]:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Không tìm thấy mô hình: {path}")
    with path.open("rb") as fh:
        payload = pickle.load(fh)
    if not isinstance(payload, dict) or "pipeline" not in payload:
        raise ValueError(f"File mô hình không đúng định dạng: {path}")
    return payload


def should_replace(old_metrics: dict[str, Any] | None, candidate_metrics: dict[str, Any]) -> bool:
    """
    Cổng chất lượng của retrain:
    - macro-F1 của ứng viên >= mô hình cũ, VÀ
    - recall lớp `blocked` không giảm.
    """
    if not old_metrics or old_metrics.get("n_samples", 0) == 0:
        return True
    return (
        candidate_metrics["macro_f1"] >= old_metrics["macro_f1"] - 1e-9
        and candidate_metrics["blocked_recall"] >= old_metrics["blocked_recall"] - 1e-9
    )


# ---------------------------------------------------------------------------
# Huấn luyện đầy đủ + báo cáo
# ---------------------------------------------------------------------------

def train_model(
    data_path: str | Path = DEFAULT_DATA_PATH,
    golden_path: str | Path | None = DEFAULT_GOLDEN_PATH,
    model_path: str | Path = DEFAULT_MODEL_PATH,
    report_path: str | Path = DEFAULT_REPORT_PATH,
    folds: int = 5,
    *,
    save: bool = True,
) -> dict[str, Any]:
    """Huấn luyện, đánh giá CV 4 thuật toán, lưu model + báo cáo JSON."""
    df = load_dataset(data_path)
    warnings_list = label_warnings(df)

    cv_results = cross_validate(df, folds=folds)
    best_algo = pick_best_algo(cv_results)
    best_oof = cross_val_predictions(df, best_algo, folds=folds)
    pipeline = fit_final_model(df, best_algo)

    report: dict[str, Any] = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "data_path": str(data_path),
        "golden_path": str(golden_path) if golden_path else None,
        "n_samples": int(len(df)),
        "label_counts": {k: int(v) for k, v in df["label"].value_counts().items()},
        "labels": list(LABELS),
        "vectorizer": {
            "analyzer": "char_wb",
            "ngram_range": [2, 5],
            "sublinear_tf": True,
        },
        "cv": {algo: cv_results[algo] for algo in ALGORITHMS},
        "cv_meta": cv_results["_meta"],
        "best_algo": best_algo,
        "best_algo_name": ALGORITHM_LABELS[best_algo],
        "best_oof_per_class": best_oof["per_class"],
        "best_oof_confusion_matrix": best_oof["confusion_matrix"],
        "labels_order": list(LABELS),
        "best_oof_accuracy": best_oof["accuracy"],
        "best_oof_macro_f1": best_oof["macro_f1"],
        "warnings": warnings_list,
        "model_path": str(model_path),
    }

    if golden_path:
        golden_df = load_dataset(golden_path, allow_empty=True)
        if golden_df.empty:
            report["golden"] = {"n_samples": 0, "note": "golden.csv rỗng — chưa có số liệu đánh giá độc lập."}
        else:
            report["golden"] = evaluate_pipeline(pipeline, golden_df)

    if save:
        save_artifact(
            pipeline,
            best_algo,
            model_path,
            metadata={
                "n_samples": int(len(df)),
                "best_oof_macro_f1": best_oof["macro_f1"],
                "trained_at": report["generated_at"],
                "data_path": str(data_path),
            },
        )
        report_path = Path(report_path)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    return {"report": report, "pipeline": pipeline, "best_algo": best_algo}


def format_cv_table(cv: dict[str, Any]) -> str:
    header = f"{'Thuật toán':<26}{'Accuracy':>20}{'Macro-F1':>20}{'Blocked recall':>20}"
    lines = [header, "-" * len(header)]
    for algo in ALGORITHMS:
        row = cv[algo]
        accuracy = f"{row['accuracy_mean']:.4f} ± {row['accuracy_std']:.4f}"
        macro_f1 = f"{row['macro_f1_mean']:.4f} ± {row['macro_f1_std']:.4f}"
        blocked = f"{row['blocked_recall_mean']:.4f} ± {row['blocked_recall_std']:.4f}"
        lines.append(f"{row['name']:<26}{accuracy:>20}{macro_f1:>20}{blocked:>20}")
    meta = cv.get("_meta", {})
    lines.append("")
    lines.append(
        f"Số mẫu: {meta.get('n_samples', '?')} | số fold: {meta.get('folds', '?')}"
    )
    return "\n".join(lines)


def format_per_class(per_class: dict[str, Any]) -> str:
    header = f"{'Nhãn':<22}{'Precision':>12}{'Recall':>12}{'F1':>12}{'Support':>10}"
    lines = [header, "-" * len(header)]
    for label in LABELS:
        row = per_class.get(label, {})
        lines.append(
            f"{label:<22}{row.get('precision', 0.0):>12.4f}{row.get('recall', 0.0):>12.4f}"
            f"{row.get('f1', 0.0):>12.4f}{row.get('support', 0):>10}"
        )
    return "\n".join(lines)


def format_confusion(matrix: list[list[int]]) -> str:
    short = [label[:10] for label in LABELS]
    width = max(10, max(len(s) for s in short) + 1)
    lines = [" " * width + "".join(s.rjust(width) for s in short)]
    for label, row in zip(short, matrix):
        lines.append(label.ljust(width) + "".join(str(v).rjust(width) for v in row))
    return "\n".join(lines)
