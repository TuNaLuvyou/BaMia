"""
Dựng ngữ cảnh "TRẠNG THÁI TÀI KHOẢN" cho nhãn `account_status`.

Nguyên tắc bảo mật: CHỈ đọc dữ liệu của chính `request.user`. Không nhận dữ liệu
booking/cart từ client (client có thể gửi sai/giả), không đọc của user khác.
"""

from __future__ import annotations

from typing import Any

from bookings.models import Booking, Cart

BOOKING_STATUS_VI = {
    "Pending": "Chờ thanh toán",
    "Confirmed": "Đã xác nhận",
    "Paid": "Đã thanh toán",
    "Cancelled": "Đã hủy",
}


def _money(value: Any) -> str:
    try:
        return f"{int(value):,}".replace(",", ".") + " VNĐ"
    except (TypeError, ValueError):
        return "không rõ"


def _date(value: Any) -> str:
    return value.strftime("%d/%m/%Y") if value else "chưa chọn ngày"


def build_account_status_context(
    user: Any, *, booking_limit: int = 5, cart_limit: int = 5
) -> str:
    """
    Trả về khối văn bản mô tả booking + giỏ hàng của chính user.
    Trả về chuỗi rỗng nếu không có user hợp lệ.
    """
    if user is None or not getattr(user, "is_authenticated", False):
        return ""

    bookings = list(
        Booking.objects.filter(user=user, deleted_at__isnull=True)
        .select_related("tour")
        .order_by("-created_at")[:booking_limit]
    )
    cart_items = list(
        Cart.objects.filter(user=user)
        .select_related("tour")
        .order_by("-added_at")[:cart_limit]
    )

    lines = ["=== TRẠNG THÁI TÀI KHOẢN (dữ liệu thật của khách đang đăng nhập) ==="]

    if bookings:
        lines.append(f"Đơn đặt tour gần nhất ({len(bookings)} đơn):")
        for booking in bookings:
            status = BOOKING_STATUS_VI.get(booking.status, booking.status)
            lines.append(
                f"- Đơn #{booking.id}: {booking.tour.title} | "
                f"khởi hành {_date(booking.date)} | {booking.number_of_people} người | "
                f"tổng {_money(booking.total_price)} | trạng thái: {status}"
            )
    else:
        lines.append("Đơn đặt tour: khách chưa có đơn nào.")

    if cart_items:
        lines.append(f"Giỏ hàng hiện có {len(cart_items)} mục:")
        for item in cart_items:
            lines.append(
                f"- {item.tour.title} | ngày dự kiến {_date(item.date)} | "
                f"{item.number_of_people} người | giá tour {_money(item.tour.price)}"
            )
    else:
        lines.append("Giỏ hàng: đang trống.")

    return "\n".join(lines)
