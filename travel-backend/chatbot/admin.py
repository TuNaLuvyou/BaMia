from django.contrib import admin

from chatbot.ml.labels import LABELS
from chatbot.models import IntentLog


class ConfidenceRangeFilter(admin.SimpleListFilter):
    title = "độ tin cậy"
    parameter_name = "confidence_range"

    def lookups(self, request, model_admin):
        return (
            ("low", "Thấp (< 0.40)"),
            ("medium", "Trung bình (0.40 – 0.60)"),
            ("high", "Cao (0.60 – 0.80)"),
            ("very_high", "Rất cao (>= 0.80)"),
        )

    def queryset(self, request, queryset):
        value = self.value()
        if value == "low":
            return queryset.filter(confidence__lt=0.4)
        if value == "medium":
            return queryset.filter(confidence__gte=0.4, confidence__lt=0.6)
        if value == "high":
            return queryset.filter(confidence__gte=0.6, confidence__lt=0.8)
        if value == "very_high":
            return queryset.filter(confidence__gte=0.8)
        return queryset


@admin.register(IntentLog)
class IntentLogAdmin(admin.ModelAdmin):
    list_display = (
        "id", "short_text", "predicted", "confidence", "routed",
        "feedback", "corrected_label", "created_at",
    )
    list_filter = (
        ConfidenceRangeFilter, "feedback", "corrected_label", "routed", "predicted",
    )
    search_fields = ("text",)
    readonly_fields = (
        "text", "predicted", "confidence", "routed", "feedback", "created_at",
    )
    date_hierarchy = "created_at"
    list_per_page = 50
    actions = []

    def has_add_permission(self, request):
        # Log chỉ sinh ra từ chatbot, không cho tạo tay.
        return False

    @admin.display(description="Câu người dùng")
    def short_text(self, obj):
        return obj.text[:80] + ("…" if len(obj.text) > 80 else "")


def _make_label_action(label):
    @admin.action(description=f"Gán nhãn đúng: {label}")
    def assign(self, request, queryset):
        updated = queryset.update(corrected_label=label)
        self.message_user(request, f"Đã gán nhãn '{label}' cho {updated} log.")

    assign.__name__ = f"assign_label_{label}"
    return assign


@admin.action(description="Xóa nhãn đúng đã gán")
def clear_label(self, request, queryset):
    updated = queryset.update(corrected_label=None)
    self.message_user(request, f"Đã xóa nhãn đúng của {updated} log.")


for _label in LABELS:
    IntentLogAdmin.actions.append(_make_label_action(_label))
IntentLogAdmin.actions.append(clear_label)
