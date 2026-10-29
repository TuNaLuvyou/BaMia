from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from chatbot.ml.console import ensure_utf8_stdout
from chatbot.models import IntentLog


class Command(BaseCommand):
    help = "Xoá log ý định cũ hơn N ngày (mặc định INTENT_LOG_RETENTION_DAYS = 90)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--days", type=int, default=None,
            help="Số ngày giữ log (mặc định lấy từ settings.INTENT_LOG_RETENTION_DAYS).",
        )

    def handle(self, *args, **options):
        ensure_utf8_stdout()
        days = options["days"]
        if days is None:
            days = getattr(settings, "INTENT_LOG_RETENTION_DAYS", 90)
        if days < 0:
            raise ValueError("--days phải >= 0")

        cutoff = timezone.now() - timedelta(days=days)
        expired = IntentLog.objects.filter(created_at__lt=cutoff)
        count = expired.count()
        expired.delete()
        self.stdout.write(
            self.style.SUCCESS(f"Đã xoá {count} log ý định cũ hơn {days} ngày.")
        )
