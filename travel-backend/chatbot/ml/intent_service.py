"""
Dịch vụ suy luận cho bộ phân loại ý định.

- Mô hình được nạp **một lần** (singleton) và giữ trong bộ nhớ, KHÔNG chạy subprocess
  hay đọc lại file mỗi lượt chat.
- Tự nạp lại nếu file `.pkl` thay đổi (sau `retrain_intent`) mà không cần restart server.
- Không import Django ở cấp module để có thể dùng trong script độc lập.
"""

from __future__ import annotations

import logging
import pickle
import threading
from pathlib import Path
from typing import Any

from chatbot.ml.labels import DEFAULT_THRESHOLDS, LABELS
from chatbot.ml.paths import DEFAULT_MODEL_PATH
from chatbot.ml.text import normalize_text

logger = logging.getLogger(__name__)

_service: "IntentService | None" = None
_service_lock = threading.Lock()


class IntentService:
    """Bọc pipeline sklearn + ngưỡng tin cậy theo nhãn."""

    def __init__(self, model_path: str | Path = DEFAULT_MODEL_PATH):
        self.model_path = Path(model_path)
        self._lock = threading.RLock()
        self._mtime: float | None = None
        self._warned_missing = False
        self.pipeline: Any = None
        self.thresholds: dict[str, float] = dict(DEFAULT_THRESHOLDS)
        self.metadata: dict[str, Any] = {}
        self.algo: str | None = None
        self.labels: list[str] = list(LABELS)

    # -- nạp mô hình -------------------------------------------------------
    @property
    def is_ready(self) -> bool:
        return self.pipeline is not None

    def load(self, force: bool = False) -> bool:
        with self._lock:
            if not self.model_path.exists():
                if not self._warned_missing:
                    logger.warning(
                        "Không tìm thấy mô hình ý định tại %s — chatbot sẽ chạy luồng cũ.",
                        self.model_path,
                    )
                    self._warned_missing = True
                self.pipeline = None
                return False

            try:
                mtime = self.model_path.stat().st_mtime
            except OSError:
                mtime = None
            if not force and self.is_ready and mtime == self._mtime:
                return True

            try:
                with self.model_path.open("rb") as fh:
                    payload = pickle.load(fh)
                if not isinstance(payload, dict) or "pipeline" not in payload:
                    raise ValueError("file mô hình không đúng định dạng")
            except Exception:  # noqa: BLE001 - lỗi file không được làm sập chatbot
                logger.exception("Không nạp được mô hình ý định: %s", self.model_path)
                self.pipeline = None
                return False

            self.pipeline = payload["pipeline"]
            self.algo = payload.get("algo")
            self.labels = list(payload.get("labels", LABELS))
            self.thresholds = {**DEFAULT_THRESHOLDS, **payload.get("thresholds", {})}
            self.metadata = payload.get("metadata", {})
            self._mtime = mtime
            self._warned_missing = False
            logger.info(
                "Đã nạp mô hình ý định (%s) từ %s", self.algo, self.model_path
            )
            return True

    def reload_if_changed(self) -> None:
        try:
            if not self.model_path.exists():
                return
            if self.model_path.stat().st_mtime != self._mtime:
                self.load()
        except OSError:
            return

    # -- suy luận ----------------------------------------------------------
    def empty_result(self) -> dict[str, Any]:
        return {
            "intent": None,
            "confidence": 0.0,
            "accepted": False,
            "threshold": None,
            "model_version": None,
            "scores": {},
        }

    def predict(self, text: str) -> dict[str, Any]:
        """
        Trả về schema ổn định:
            {"intent": str|None, "confidence": float, "accepted": bool,
             "threshold": float|None, "model_version": str|None, "scores": dict}
        `accepted` = confidence >= ngưỡng của nhãn dự đoán.
        """
        if not self.is_ready:
            return self.empty_result()

        normalized = normalize_text(text)
        if not normalized:
            return self.empty_result()

        with self._lock:
            pipeline = self.pipeline
            try:
                if hasattr(pipeline, "predict_proba"):
                    probabilities = pipeline.predict_proba([normalized])[0]
                    classes = list(pipeline.classes_)
                    scores = {
                        str(label): float(prob) for label, prob in zip(classes, probabilities)
                    }
                else:  # pragma: no cover - các mô hình đang dùng đều có predict_proba
                    label = str(pipeline.predict([normalized])[0])
                    scores = {label: 1.0}
            except Exception:  # noqa: BLE001
                logger.exception("Lỗi khi dự đoán ý định")
                return self.empty_result()

        intent = max(scores, key=scores.get)
        confidence = float(scores[intent])
        threshold = float(self.thresholds.get(intent, 0.5))
        return {
            "intent": intent,
            "confidence": round(confidence, 4),
            "accepted": confidence >= threshold,
            "threshold": threshold,
            "model_version": self.metadata.get("trained_at"),
            "scores": {key: round(value, 4) for key, value in scores.items()},
        }


def _resolve_model_path(model_path: str | Path | None = None) -> Path:
    if model_path:
        return Path(model_path)
    try:
        from django.conf import settings

        configured = getattr(settings, "INTENT_MODEL_PATH", None)
        if configured:
            return Path(configured)
    except Exception:  # noqa: BLE001 - chạy ngoài Django
        pass
    return DEFAULT_MODEL_PATH


def get_intent_service(
    model_path: str | Path | None = None, *, force_reload: bool = False
) -> IntentService:
    """Singleton: nạp mô hình một lần, dùng lại cho mọi request."""
    global _service
    resolved = _resolve_model_path(model_path)
    with _service_lock:
        if _service is None or _service.model_path != resolved:
            _service = IntentService(resolved)
            _service.load(force=True)
        elif force_reload:
            _service.load(force=True)
        else:
            _service.reload_if_changed()
    return _service


def reset_intent_service() -> None:
    """Dùng trong test để xoá singleton."""
    global _service
    with _service_lock:
        _service = None


def routing_enabled() -> bool:
    """Đọc cờ INTENT_ROUTING_ENABLED từ Django settings (mặc định True)."""
    try:
        from django.conf import settings

        return bool(getattr(settings, "INTENT_ROUTING_ENABLED", True))
    except Exception:  # noqa: BLE001
        return True
