from django.test import TestCase
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from tours.models import Destination, Tour
from bookings.models import Booking, Cart


def auth_headers(user):
    refresh = RefreshToken.for_user(user)
    return {'HTTP_AUTHORIZATION': f'Bearer {refresh.access_token}'}


class BookingSlotTests(TestCase):
    """Kiểm tra logic trừ/hoàn available_slots khi đặt, hủy, xóa mềm booking."""

    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='StrongPass123!')
        self.client = APIClient()
        dest = Destination.objects.create(name='Đà Lạt', description='Thành phố sương mù')
        self.tour = Tour.objects.create(
            title='Tour Đà Lạt',
            description='Khám phá thành phố ngàn hoa',
            location=dest,
            price=1000,
            duration='3 days 2 nights',
            available_slots=5,
        )
        self.date = timezone.now().date() + timedelta(days=5)

    def test_create_booking_decrements_slots_and_computes_price(self):
        resp = self.client.post(
            '/api/bookings/',
            {'tour': self.tour.id, 'date': self.date.isoformat(), 'number_of_people': 2},
            **auth_headers(self.user),
        )
        self.assertEqual(resp.status_code, 201)
        self.tour.refresh_from_db()
        self.assertEqual(self.tour.available_slots, 3)

        booking = Booking.objects.get(id=resp.data['id'])
        self.assertEqual(booking.total_price, 2000)
        self.assertEqual(booking.status, 'Pending')
        self.assertEqual(booking.user, self.user)

    def test_create_booking_insufficient_slots_rejected(self):
        self.tour.available_slots = 2
        self.tour.save(update_fields=['available_slots'])

        resp = self.client.post(
            '/api/bookings/',
            {'tour': self.tour.id, 'date': self.date.isoformat(), 'number_of_people': 3},
            **auth_headers(self.user),
        )
        self.assertEqual(resp.status_code, 400)
        self.tour.refresh_from_db()
        self.assertEqual(self.tour.available_slots, 2)
        self.assertFalse(Booking.objects.exists())

    def test_soft_delete_moves_to_trash_and_restores_slots(self):
        booking = Booking.objects.create(
            user=self.user, tour=self.tour, date=self.date,
            number_of_people=2, total_price=2000,
        )
        self.tour.available_slots = 3
        self.tour.save(update_fields=['available_slots'])

        resp = self.client.delete(f'/api/bookings/{booking.id}/', **auth_headers(self.user))
        self.assertEqual(resp.status_code, 200)
        booking.refresh_from_db()
        self.assertIsNotNone(booking.deleted_at)
        self.tour.refresh_from_db()
        self.assertEqual(self.tour.available_slots, 5)

    def test_trash_restore_flow(self):
        booking = Booking.objects.create(
            user=self.user, tour=self.tour, date=self.date,
            number_of_people=2, total_price=2000, deleted_at=timezone.now(),
        )
        self.tour.available_slots = 5
        self.tour.save(update_fields=['available_slots'])

        trash = self.client.get('/api/bookings/trash/', **auth_headers(self.user))
        self.assertEqual(trash.status_code, 200)
        self.assertEqual(len(trash.data), 1)

        resp = self.client.patch(f'/api/bookings/{booking.id}/restore/', **auth_headers(self.user))
        self.assertEqual(resp.status_code, 200)
        booking.refresh_from_db()
        self.assertIsNone(booking.deleted_at)
        self.tour.refresh_from_db()
        self.assertEqual(self.tour.available_slots, 3)

    def test_restore_fails_when_slots_not_available(self):
        booking = Booking.objects.create(
            user=self.user, tour=self.tour, date=self.date,
            number_of_people=4, total_price=4000, deleted_at=timezone.now(),
        )
        self.tour.available_slots = 3
        self.tour.save(update_fields=['available_slots'])

        resp = self.client.patch(f'/api/bookings/{booking.id}/restore/', **auth_headers(self.user))
        self.assertEqual(resp.status_code, 400)
        booking.refresh_from_db()
        self.assertIsNotNone(booking.deleted_at)

    def test_cancel_pending_booking(self):
        booking = Booking.objects.create(
            user=self.user, tour=self.tour, date=self.date,
            number_of_people=2, total_price=2000,
        )
        self.tour.available_slots = 3
        self.tour.save(update_fields=['available_slots'])

        resp = self.client.patch(f'/api/bookings/{booking.id}/cancel/', **auth_headers(self.user))
        self.assertEqual(resp.status_code, 200)
        booking.refresh_from_db()
        self.assertIsNotNone(booking.deleted_at)
        self.tour.refresh_from_db()
        self.assertEqual(self.tour.available_slots, 5)

    def test_cannot_cancel_non_pending_booking(self):
        booking = Booking.objects.create(
            user=self.user, tour=self.tour, date=self.date,
            number_of_people=1, total_price=1000, status='Confirmed',
        )
        resp = self.client.patch(f'/api/bookings/{booking.id}/cancel/', **auth_headers(self.user))
        self.assertEqual(resp.status_code, 400)
        self.tour.refresh_from_db()
        self.assertEqual(self.tour.available_slots, 5)

    def test_permanent_delete_and_empty_trash(self):
        b1 = Booking.objects.create(
            user=self.user, tour=self.tour, date=self.date,
            number_of_people=1, total_price=1000, deleted_at=timezone.now(),
        )
        b2 = Booking.objects.create(
            user=self.user, tour=self.tour, date=self.date,
            number_of_people=1, total_price=1000, deleted_at=timezone.now(),
        )

        resp = self.client.delete(f'/api/bookings/{b1.id}/permanent-delete/', **auth_headers(self.user))
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(Booking.objects.filter(id=b1.id).exists())

        resp = self.client.delete('/api/bookings/empty-trash/', **auth_headers(self.user))
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(Booking.objects.filter(id=b2.id).exists())

    def test_user_cannot_see_or_manage_others_bookings(self):
        other = User.objects.create_user(username='other', password='StrongPass123!')
        booking = Booking.objects.create(
            user=other, tour=self.tour, date=self.date,
            number_of_people=1, total_price=1000,
        )

        resp = self.client.get('/api/bookings/', **auth_headers(self.user))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data), 0)

        resp = self.client.delete(f'/api/bookings/{booking.id}/', **auth_headers(self.user))
        self.assertEqual(resp.status_code, 404)


class CartTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='cartuser', password='StrongPass123!')
        self.client = APIClient()
        dest = Destination.objects.create(name='Hội An', description='Phố cổ')
        self.tour = Tour.objects.create(
            title='Tour Hội An', description='desc', location=dest,
            price=500, duration='2 days', available_slots=10,
        )
        self.date = timezone.now().date() + timedelta(days=3)

    def test_add_and_list_cart(self):
        resp = self.client.post(
            '/api/cart/',
            {'tour': self.tour.id, 'date': self.date.isoformat(), 'number_of_people': 2},
            **auth_headers(self.user),
        )
        self.assertEqual(resp.status_code, 201)

        resp = self.client.get('/api/cart/', **auth_headers(self.user))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data), 1)
        self.assertEqual(resp.data[0]['user'], self.user.id)
        self.assertEqual(resp.data[0]['number_of_people'], 2)

    def test_cart_isolated_per_user(self):
        other = User.objects.create_user(username='other', password='StrongPass123!')
        self.client.post(
            '/api/cart/',
            {'tour': self.tour.id, 'date': self.date.isoformat(), 'number_of_people': 1},
            **auth_headers(other),
        )
        resp = self.client.get('/api/cart/', **auth_headers(self.user))
        self.assertEqual(len(resp.data), 0)


class MyItineraryTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='itinuser', password='StrongPass123!')
        self.client = APIClient()
        dest = Destination.objects.create(name='Sapa', description='Cao nguyên')
        self.tour = Tour.objects.create(
            title='Tour Sapa', description='desc', location=dest,
            price=800, duration='3 days 2 nights', available_slots=10,
        )
        self.date = timezone.now().date() + timedelta(days=4)

    def test_itinerary_contains_booking_and_cart_events(self):
        Booking.objects.create(
            user=self.user, tour=self.tour, date=self.date,
            number_of_people=1, total_price=800,
        )
        Cart.objects.create(user=self.user, tour=self.tour, date=self.date, number_of_people=1)

        resp = self.client.get('/api/my-itinerary/', **auth_headers(self.user))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data), 2)

    def test_itinerary_requires_auth(self):
        resp = self.client.get('/api/my-itinerary/')
        self.assertEqual(resp.status_code, 401)
