from rest_framework.permissions import BasePermission, SAFE_METHODS


class IsAdminUserOrReadOnly(BasePermission):
    """
    Cho phép mọi người đọc (GET), chỉ admin (staff) mới được tạo/sửa/xoá.
    Dùng cho các resource dữ liệu hệ thống: Tour, Category, Destination.
    """

    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True
        return bool(request.user and request.user.is_staff)


class IsOwnerOrAdminOrReadOnly(BasePermission):
    """
    Cho phép đọc công khai; chỉ chủ sở hữu (hoặc admin) mới được sửa/xoá.
    Dùng cho Review.
    """

    def has_object_permission(self, request, view, obj):
        if request.method in SAFE_METHODS:
            return True
        return bool(
            request.user
            and (request.user.is_staff or obj.user_id == request.user.id)
        )
