from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from chatbot.ml.console import ensure_utf8_stdout
from chatbot.ml.intent_core import DatasetError
from chatbot.ml.paths import (
    DEFAULT_DATA_PATH,
    DEFAULT_GOLDEN_PATH,
    DEFAULT_MODEL_PATH,
    DEFAULT_REPORT_PATH,
)
from chatbot.ml.train_intent import run_training


class Command(BaseCommand):
    help = (
        "Huấn luyện bộ phân loại ý định chatbot: so sánh 4 thuật toán bằng stratified k-fold, "
        "lưu mô hình .pkl và báo cáo JSON."
    )

    def add_arguments(self, parser):
        parser.add_argument("--data", default=None, help="CSV huấn luyện (text,label)")
        parser.add_argument("--golden", default=None, help="CSV đánh giá độc lập (text,label)")
        parser.add_argument("--output", default=None, help="Đường dẫn file mô hình .pkl")
        parser.add_argument("--report", default=None, help="Đường dẫn báo cáo JSON")
        parser.add_argument("--folds", type=int, default=5, help="Số fold (mặc định 5)")

    def handle(self, *args, **options):
        ensure_utf8_stdout()
        data_path = options["data"] or getattr(settings, "INTENT_DATA_PATH", str(DEFAULT_DATA_PATH))
        golden_path = options["golden"] or getattr(
            settings, "INTENT_GOLDEN_PATH", str(DEFAULT_GOLDEN_PATH)
        )
        model_path = options["output"] or getattr(
            settings, "INTENT_MODEL_PATH", str(DEFAULT_MODEL_PATH)
        )
        report_path = options["report"] or str(DEFAULT_REPORT_PATH)

        try:
            _, lines = run_training(
                data_path=data_path,
                golden_path=golden_path,
                model_path=model_path,
                report_path=report_path,
                folds=options["folds"],
            )
        except DatasetError as exc:
            raise CommandError(str(exc)) from exc
        except FileNotFoundError as exc:
            raise CommandError(str(exc)) from exc

        for line in lines:
            self.stdout.write(line)
        self.stdout.write(self.style.SUCCESS("\nHoàn tất huấn luyện bộ phân loại ý định."))
