from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from .models import Booking, Cart
from .serializers import BookingSerializer, CartSerializer
import re
from rest_framework.decorators import action
from rest_framework import status
from datetime import timedelta
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAdminUser
from django.contrib.auth.models import User
from tours.models import Tour
from django.utils import timezone
from django.db import transaction
from rest_framework.exceptions import ValidationError

class BookingViewSet(viewsets.ModelViewSet):
    serializer_class = BookingSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """Mặc định chỉ trả booking chưa bị xoá (không trong thùng rác)."""
        return Booking.objects.filter(
            user=self.request.user,
            deleted_at__isnull=True
        )

    def perform_create(self, serializer):
        tour_instance = serializer.validated_data['tour']
        people = serializer.validated_data.get('number_of_people', 1)

        with transaction.atomic():
            tour = Tour.objects.select_for_update().get(id=tour_instance.id)
            if tour.available_slots < people:
                raise ValidationError({'detail': f'Không đủ chỗ. Chỉ còn {tour.available_slots} chỗ trống.'})
            
            tour.available_slots -= people
            tour.save(update_fields=['available_slots'])

            total_price = tour.price * people
            serializer.save(user=self.request.user, total_price=total_price, tour=tour)

    def destroy(self, request, *args, **kwargs):
        """Xoá mềm: chuyển vào thùng rác thay vì xoá vĩnh viễn."""
        with transaction.atomic():
            booking = self.get_object()
            if not booking.deleted_at:
                booking.deleted_at = timezone.now()
                booking.save(update_fields=['deleted_at'])
                
                # Restore slots if it was not Cancelled
                if booking.status != 'Cancelled':
                    tour = Tour.objects.select_for_update().get(id=booking.tour.id)
                    tour.available_slots += booking.number_of_people
                    tour.save(update_fields=['available_slots'])

        return Response(
            {'status': 'Đã chuyển vào thùng rác', 'id': booking.id},
            status=status.HTTP_200_OK
        )

    @action(detail=False, methods=['get'], url_path='trash')
    def trash(self, request):
        """Lấy danh sách booking trong thùng rác của user."""
        trashed = Booking.objects.filter(
            user=request.user,
            deleted_at__isnull=False
        ).order_by('-deleted_at')
        serializer = self.get_serializer(trashed, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['patch'], url_path='restore')
    def restore(self, request, pk=None):
        """Khôi phục booking từ thùng rác."""
        with transaction.atomic():
            booking = Booking.objects.select_for_update().filter(
                id=pk, user=request.user, deleted_at__isnull=False
            ).first()
            if not booking:
                return Response(
                    {'error': 'Không tìm thấy đơn hàng trong thùng rác'},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            if booking.status != 'Cancelled':
                tour = Tour.objects.select_for_update().get(id=booking.tour.id)
                if tour.available_slots < booking.number_of_people:
                    return Response(
                        {'error': f'Không đủ chỗ để khôi phục. Tour chỉ còn {tour.available_slots} chỗ trống.'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                tour.available_slots -= booking.number_of_people
                tour.save(update_fields=['available_slots'])

            booking.deleted_at = None
            booking.save(update_fields=['deleted_at'])
            return Response({'status': 'Đã khôi phục', 'id': booking.id})

    @action(detail=True, methods=['delete'], url_path='permanent-delete')
    def permanent_delete(self, request, pk=None):
        """Xoá vĩnh viễn khỏi thùng rác."""
        booking = Booking.objects.filter(
            id=pk, user=request.user, deleted_at__isnull=False
        ).first()
        if not booking:
            return Response(
                {'error': 'Không tìm thấy đơn hàng trong thùng rác'},
                status=status.HTTP_404_NOT_FOUND
            )
        booking_id = booking.id
        booking.delete()
        return Response(
            {'status': 'Đã xoá vĩnh viễn', 'id': booking_id},
            status=status.HTTP_200_OK
        )

    @action(detail=False, methods=['delete'], url_path='empty-trash')
    def empty_trash(self, request):
        """Xoá toàn bộ thùng rác của user."""
        count, _ = Booking.objects.filter(
            user=request.user,
            deleted_at__isnull=False
        ).delete()
        return Response({'status': f'Đã xoá vĩnh viễn {count} đơn hàng'})

    @action(detail=True, methods=['patch'], url_path='cancel')
    def cancel(self, request, pk=None):
        with transaction.atomic():
            booking = self.get_object()
            if booking.status == 'Pending':
                if not booking.deleted_at:
                    # Chuyển vào thùng rác thay vì xoá luôn
                    booking.deleted_at = timezone.now()
                    booking.save(update_fields=['deleted_at'])
                    
                    # Hoàn lại chỗ
                    tour = Tour.objects.select_for_update().get(id=booking.tour.id)
                    tour.available_slots += booking.number_of_people
                    tour.save(update_fields=['available_slots'])

                return Response(
                    {'status': 'Đã hủy đơn hàng và chuyển vào thùng rác'},
                    status=status.HTTP_200_OK
                )
            return Response(
                {'error': 'Không thể hủy đơn hàng này'},
                status=status.HTTP_400_BAD_REQUEST
            )

    @action(detail=True, methods=['patch'], url_path='toggle-calendar')
    def toggle_calendar(self, request, pk=None):
        booking = self.get_object()
        show = request.data.get('show_on_calendar')
        if show is None:
            booking.show_on_calendar = not booking.show_on_calendar
        else:
            booking.show_on_calendar = bool(show)
        booking.save(update_fields=['show_on_calendar'])
        return Response({
            'id': booking.id,
            'show_on_calendar': booking.show_on_calendar
        })


class CartViewSet(viewsets.ModelViewSet):
    serializer_class = CartSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Cart.objects.filter(user=self.request.user).order_by('-added_at')

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    @action(detail=True, methods=['patch'], url_path='toggle-calendar')
    def toggle_calendar(self, request, pk=None):
        cart_item = self.get_object()
        show = request.data.get('show_on_calendar')
        if show is None:
            cart_item.show_on_calendar = not cart_item.show_on_calendar
        else:
            cart_item.show_on_calendar = bool(show)
        cart_item.save(update_fields=['show_on_calendar'])
        return Response({
            'id': cart_item.id,
            'show_on_calendar': cart_item.show_on_calendar
        })


class MyItineraryView(APIView):
    permission_classes = [IsAuthenticated]

    def get_end_date(self, start_date, duration_str):
        if not start_date:
            return None
        match = re.search(r'\d+', str(duration_str))
        days = int(match.group()) if match else 1
        return start_date + timedelta(days=days - 1)

    def get(self, request):
        bookings = Booking.objects.filter(
            user=request.user,
            show_on_calendar=True,
            deleted_at__isnull=True
        ).exclude(status='Cancelled')

        cart_items = Cart.objects.filter(
            user=request.user,
            show_on_calendar=True
        )

        events = []

        for b in bookings:
            if b.date:
                end_date = self.get_end_date(b.date, b.tour.duration)

                if b.status == 'Pending':
                    bg_color = '#F59E0B'
                    border_color = '#D97706'
                    label = f"[Chờ thanh toán] {b.tour.title}"
                elif b.status == 'Paid':
                    bg_color = '#10B981'
                    border_color = '#059669'
                    label = f"[Đã thanh toán] {b.tour.title}"
                else:
                    bg_color = '#34D399'
                    border_color = '#10B981'
                    label = f"[Đã đặt] {b.tour.title}"

                events.append({
                    'id': f'booking_{b.id}',
                    'title': label,
                    'start': b.date.strftime('%Y-%m-%d'),
                    'end': (end_date + timedelta(days=1)).strftime('%Y-%m-%d'),
                    'allDay': True,
                    'display': 'block',
                    'backgroundColor': bg_color,
                    'borderColor': border_color,
                    'extendedProps': {
                        'status': b.status,
                        'tour_id': b.tour.id,
                        'location_name': b.tour.location.name if b.tour.location else ''
                    }
                })

        for c in cart_items:
            if c.date:
                end_date = self.get_end_date(c.date, c.tour.duration)
                events.append({
                    'id': f'cart_{c.id}',
                    'title': f"[Giỏ hàng] {c.tour.title}",
                    'start': c.date.strftime('%Y-%m-%d'),
                    'end': (end_date + timedelta(days=1)).strftime('%Y-%m-%d'),
                    'allDay': True,
                    'display': 'block',
                    'backgroundColor': '#F97316',
                    'borderColor': '#EA580C',
                    'extendedProps': {
                        'status': 'in_cart',
                        'tour_id': c.tour.id,
                        'location_name': c.tour.location.name if c.tour.location else ''
                    }
                })

        return Response(events)


class AdminDashboardView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        total_users = User.objects.count()
        total_tours = Tour.objects.count()
        total_bookings = Booking.objects.count()

        confirmed_bookings = Booking.objects.filter(status__in=['Confirmed', 'Paid'])
        revenue = sum([booking.total_price for booking in confirmed_bookings])

        recent_bookings = Booking.objects.order_by('-created_at')[:5]
        recent_data = [{
            'id': b.id,
            'user': b.user.username,
            'tour': b.tour.title,
            'date': b.date.strftime('%d/%m/%Y') if b.date else 'Chưa chọn',
            'status': b.status,
            'total': b.total_price
        } for b in recent_bookings]

        return Response({
            'total_users': total_users,
            'total_tours': total_tours,
            'total_bookings': total_bookings,
            'revenue': revenue,
            'recent_bookings': recent_data
        })