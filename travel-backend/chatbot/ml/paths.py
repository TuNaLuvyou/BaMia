"""Đường dẫn mặc định của mô-đun ML (không import thư viện nặng)."""

from pathlib import Path

ML_DIR = Path(__file__).resolve().parent
DATA_DIR = ML_DIR / "data"
ARTIFACTS_DIR = ML_DIR / "artifacts"
BACKUP_DIR = ARTIFACTS_DIR / "backup"

DEFAULT_DATA_PATH = DATA_DIR / "intents.csv"
DEFAULT_GOLDEN_PATH = DATA_DIR / "golden.csv"
DEFAULT_MODEL_PATH = ARTIFACTS_DIR / "intent_model.pkl"
DEFAULT_REPORT_PATH = ARTIFACTS_DIR / "intent_report.json"
DEFAULT_BASELINE_REPORT_PATH = ARTIFACTS_DIR / "baseline_report.json"
DEFAULT_LATENCY_REPORT_PATH = ARTIFACTS_DIR / "latency_report.json"
