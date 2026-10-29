from django.core.management.base import BaseCommand

from chatbot.feedback import DEFAULT_EXPORT_PATH, write_feedback_csv
from chatbot.ml.console import ensure_utf8_stdout


class Command(BaseCommand):
    help = (
        "Xuất các log đã được admin gán corrected_label ra CSV (text,label) "
        "để dùng cho retrain_intent."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--output", default=str(DEFAULT_EXPORT_PATH),
            help="Đường dẫn CSV đầu ra.",
        )

    def handle(self, *args, **options):
        ensure_utf8_stdout()
        path, count = write_feedback_csv(options["output"])
        self.stdout.write(
            self.style.SUCCESS(f"Đã xuất {count} dòng phản hồi đã duyệt ra {path}.")
        )
