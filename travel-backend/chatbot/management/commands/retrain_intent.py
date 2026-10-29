from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from chatbot.ml.console import ensure_utf8_stdout
from chatbot.ml.paths import (
    BACKUP_DIR,
    DEFAULT_DATA_PATH,
    DEFAULT_GOLDEN_PATH,
    DEFAULT_MODEL_PATH,
)
from chatbot.ml.retrain_intent import run_retrain


class Command(BaseCommand):
    help = (
        "Huấn luyện lại bộ phân loại ý định: gộp dữ liệu gốc + phản hồi đã duyệt, "
        "đánh giá đối đầu trên golden.csv và chỉ thay thế nếu vượt qua cổng chất lượng."
    )

    def add_arguments(self, parser):
        parser.add_argument("--data", default=None, help="CSV dữ liệu gốc (mặc định intents.csv)")
        parser.add_argument("--feedback", default=None, help="CSV phản hồi đã duyệt (hoặc tự đọc DB)")
        parser.add_argument("--golden", default=None, help="CSV đánh giá độc lập (golden.csv)")
        parser.add_argument("--model", default=None, help="Đường dẫn file mô hình .pkl")
        parser.add_argument("--backup-dir", default=None, help="Thư mục sao lưu mô hình cũ")
        parser.add_argument("--folds", type=int, default=5, help="Số fold CV")
        parser.add_argument(
            "--dry-run", action="store_true", help="Chỉ đánh giá và lập báo cáo, không thay thế mô hình"
        )

    def handle(self, *args, **options):
        ensure_utf8_stdout()
        data_path = options["data"] or getattr(settings, "INTENT_DATA_PATH", str(DEFAULT_DATA_PATH))
        golden_path = options["golden"] or getattr(
            settings, "INTENT_GOLDEN_PATH", str(DEFAULT_GOLDEN_PATH)
        )
        model_path = options["model"] or getattr(
            settings, "INTENT_MODEL_PATH", str(DEFAULT_MODEL_PATH)
        )
        backup_dir = options["backup_dir"] or str(BACKUP_DIR)

        try:
            report = run_retrain(
                data_path=data_path,
                feedback_path=options["feedback"],
                golden_path=golden_path,
                model_path=model_path,
                backup_dir=backup_dir,
                folds=options["folds"],
                dry_run=options["dry_run"],
            )
        except Exception as exc:
            raise CommandError(str(exc)) from exc

        self.stdout.write("=" * 75)
        self.stdout.write(f"Trạng thái : {report['decision']}")
        self.stdout.write(f"Lý do      : {report['gate_reason']}")
        self.stdout.write(f"Ứng viên   : {report['candidate']['algo_name']}")
        self.stdout.write(
            f"Mẫu dữ liệu: {report['data']['total_merged_samples']} "
            f"(Gốc: {report['data']['base_samples']} + Phản hồi: {report['data']['feedback_samples']})"
        )
        if report["backup_path"]:
            self.stdout.write(f"Bản sao lưu: {report['backup_path']}")
        self.stdout.write(f"Báo cáo JSON: {report['report_json_path']}")
        self.stdout.write(f"Báo cáo MD  : {report['report_md_path']}")
        self.stdout.write("=" * 75)

        if report["passed_gate"]:
            self.stdout.write(self.style.SUCCESS("Quy trình retrain hoàn tất thành công."))
        else:
            self.stdout.write(self.style.WARNING("Ứng viên không đạt cổng chất lượng, mô hình cũ được giữ nguyên."))
