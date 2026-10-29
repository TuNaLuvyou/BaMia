from django.db import models

from chatbot.ml.labels import LABEL_CHOICES


class IntentLog(models.Model):
    """
    Log một lượt phân loại ý định — KHÔNG lưu user id hay bất kỳ thông tin định danh nào.

    - `text`: câu người dùng (cắt 500 ký tự).
    - `predicted`: nhãn mô hình dự đoán.
    - `confidence`: xác suất của nhãn dự đoán.
    - `routed`: mô hình có vượt ngưỡng để định tuyến hay không.
    - `corrected_label`: nhãn đúng do admin gán (nguồn dữ liệu cho retrain).
    - `feedback`: -1 (không hữu ích), 0 (trung lập), +1 (hữu ích); null = chưa đánh giá.
    """

    FEEDBACK_CHOICES = (
        (-1, "Không hữu ích"),
        (0, "Trung lập"),
        (1, "Hữu ích"),
    )

    text = models.CharField(max_length=500)
    predicted = models.CharField(
        max_length=32, blank=True, choices=LABEL_CHOICES, verbose_name="Nhãn dự đoán"
    )
    confidence = models.FloatField(default=0.0, verbose_name="Độ tin cậy")
    routed = models.BooleanField(default=False, verbose_name="Đã định tuyến")
    corrected_label = models.CharField(
        max_length=32, blank=True, null=True, choices=LABEL_CHOICES,
        verbose_name="Nhãn đúng (admin gán)",
    )
    feedback = models.SmallIntegerField(
        null=True, blank=True, choices=FEEDBACK_CHOICES, verbose_name="Phản hồi"
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Log ý định"
        verbose_name_plural = "Log ý định"
        indexes = [
            models.Index(fields=["predicted", "created_at"]),
        ]

    def __str__(self):
        return f"#{self.pk} {self.predicted or '?'} ({self.confidence:.2f})"
