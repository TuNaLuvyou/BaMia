from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework import status
from rest_framework.exceptions import ValidationError
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from .models import Transaction
from bookings.models import Booking, Cart
from tours.models import Tour
from decimal import Decimal
import hmac

class CreatePaymentView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        cart_item_ids = request.data.get('cart_item_ids', [])
        payment_method = request.data.get('payment_method', 'vnpay')

        if not isinstance(cart_item_ids, list) or not cart_item_ids:
            return Response({'error': 'Không có tour nào được chọn'}, status=status.HTTP_400_BAD_REQUEST)

        # Lấy các item trong giỏ hàng của chính user
        cart_items = list(Cart.objects.filter(id__in=cart_item_ids, user=request.user))
        if not cart_items:
            return Response({'error': 'Giỏ hàng không hợp lệ'}, status=status.HTTP_400_BAD_REQUEST)

        total_amount = Decimal(0)
        new_bookings = []

        try:
            with transaction.atomic():
                # Chuyển Cart -> Booking (trạng thái Pending), kiểm tra & trừ chỗ trống
                for item in cart_items:
                    tour = Tour.objects.select_for_update().get(id=item.tour.id)
                    if tour.available_slots < item.number_of_people:
                        raise ValidationError(f'Không đủ chỗ cho tour "{tour.title}". Chỉ còn {tour.available_slots} chỗ trống.')

                    tour.available_slots -= item.number_of_people
                    tour.save(update_fields=['available_slots'])

                    price = tour.price * item.number_of_people
                    total_amount += price

                    booking = Booking.objects.create(
                        user=request.user,
                        tour=tour,
                        date=item.date or timezone.localdate(),
                        number_of_people=item.number_of_people,
                        total_price=price,
                        status='Pending'
                    )
                    new_bookings.append(booking)

                # KHÔNG xóa cart items ở đây - chỉ xóa sau khi thanh toán thành công (trong webhook)
                # Tạo Transaction - lưu lại cart_item_ids để xóa sau
                payment_txn = Transaction.objects.create(
                    user=request.user,
                    amount=total_amount,
                    payment_method=payment_method,
                    status='Pending',
                    cart_item_ids=list(cart_item_ids)  # Lưu để webhook biết cần xóa cart nào
                )
                payment_txn.bookings.set(new_bookings)
        except (ValidationError, Tour.DoesNotExist) as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

        # Trả về transaction_id cho Frontend mở Sandbox
        return Response({
            'message': 'Khởi tạo thanh toán thành công',
            'transaction_id': payment_txn.id,
            'total_amount': total_amount,
            'payment_method': payment_method
        })

class WebhookIPNView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        # Xác thực chữ ký IPN để chống giả mạo.
        # LƯU Ý: trong bản demo/sandbox, chữ ký được frontend gửi lên nên chỉ chống giả mạo cơ bản.
        # Khi triển khai thật, webhook phải được xác thực phía server bởi nhà cung cấp thanh toán,
        # KHÔNG bao giờ đặt PAYMENT_WEBHOOK_SECRET thật vào frontend.
        signature = str(request.data.get('signature', ''))
        expected_signature = getattr(settings, 'PAYMENT_WEBHOOK_SECRET', 'mock_signature_12345')
        if not hmac.compare_digest(signature, expected_signature):
            return Response({'error': 'Chữ ký không hợp lệ'}, status=status.HTTP_403_FORBIDDEN)

        transaction_id = request.data.get('transaction_id')
        status_code = request.data.get('status')

        with transaction.atomic():
            try:
                payment_txn = Transaction.objects.select_for_update().get(id=transaction_id)
            except (Transaction.DoesNotExist, ValueError):
                return Response({'error': 'Giao dịch không tồn tại'}, status=status.HTTP_404_NOT_FOUND)

            # Chống xử lý trùng lặp IPN
            if payment_txn.status != 'Pending':
                return Response({'message': 'IPN Processed: Giao dịch đã được xử lý trước đó'})

            if status_code == 'success':
                payment_txn.status = 'Success'
                payment_txn.save()

                # Cập nhật tất cả booking của transaction này sang Paid
                payment_txn.bookings.all().update(status='Paid')

                # Xóa cart items sau khi thanh toán thành công
                Cart.objects.filter(id__in=payment_txn.cart_item_ids, user=payment_txn.user).delete()

                return Response({'message': 'IPN Processed: Cập nhật thành công sang Paid'})
            else:
                payment_txn.status = 'Failed'
                payment_txn.save()
                # Khi hủy/thất bại → GIỮ LẠI cart items và booking ở trạng thái Pending
                # để khách có thể thanh toán lại (RetryPaymentView chỉ nhận booking Pending)
                return Response({'message': 'IPN Processed: Giao dịch thất bại'})


class RetryPaymentView(APIView):
    """API để thanh toán lại các Booking đang Pending (không cần Cart)"""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        booking_ids = request.data.get('booking_ids', [])
        payment_method = request.data.get('payment_method', 'vnpay')

        if not booking_ids:
            return Response({'error': 'Không có đơn hàng nào được chọn'}, status=status.HTTP_400_BAD_REQUEST)

        # Chỉ lấy Pending bookings của user
        bookings = Booking.objects.filter(id__in=booking_ids, user=request.user, status='Pending')
        if not bookings.exists():
            return Response({'error': 'Không tìm thấy đơn hàng Pending hợp lệ'}, status=status.HTTP_400_BAD_REQUEST)

        total_amount = sum((b.total_price for b in bookings), Decimal(0))

        # Tạo Transaction mới liên kết với các booking đang chờ
        transaction = Transaction.objects.create(
            user=request.user,
            amount=total_amount,
            payment_method=payment_method,
            status='Pending',
            cart_item_ids=[]  # Không có cart items, giỏ hàng đã xử lý trước
        )
        transaction.bookings.set(bookings)

        return Response({
            'message': 'Khởi tạo thanh toán lại thành công',
            'transaction_id': transaction.id,
            'total_amount': total_amount,
            'payment_method': payment_method
        })
