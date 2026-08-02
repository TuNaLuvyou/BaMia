from django.test import TestCase
from django.contrib.auth.models import User
from django.conf import settings
from django.utils import timezone
from datetime import timedelta
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from tours.models import Destination, Tour
from bookings.models import Booking, Cart
from payments.models import Transaction


def auth_headers(user):
    refresh = RefreshToken.for_user(user)
    return {'HTTP_AUTHORIZATION': f'Bearer {refresh.access_token}'}


class PaymentFlowTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='payer', password='StrongPass123!')
        self.client = APIClient()
        dest = Destination.objects.create(name='Nha Trang', description='Biển xanh')
        self.tour = Tour.objects.create(
            title='Tour Nha Trang', description='desc', location=dest,
            price=500, duration='2 days', available_slots=10,
        )
        self.date = timezone.now().date() + timedelta(days=3)

    def test_create_payment_from_cart(self):
        cart = Cart.objects.create(user=self.user, tour=self.tour, date=self.date, number_of_people=2)
        self.tour.available_slots = 5
        self.tour.save(update_fields=['available_slots'])

        resp = self.client.post(
            '/api/payments/create/',
            {'cart_item_ids': [cart.id], 'payment_method': 'vnpay'},
            format='json',
            **auth_headers(self.user),
        )
        self.assertEqual(resp.status_code, 200)
        self.assertIn('transaction_id', resp.data)
        self.assertEqual(Transaction.objects.count(), 1)
        self.assertEqual(Booking.objects.count(), 1)
        self.tour.refresh_from_db()
        self.assertEqual(self.tour.available_slots, 3)

    def test_create_payment_requires_auth(self):
        resp = self.client.post(
            '/api/payments/create/', {'cart_item_ids': [1]}, format='json'
        )
        self.assertEqual(resp.status_code, 401)


class WebhookIPNTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='payer', password='StrongPass123!')
        self.client = APIClient()
        dest = Destination.objects.create(name='Nha Trang', description='Biển xanh')
        self.tour = Tour.objects.create(
            title='Tour Nha Trang', description='desc', location=dest,
            price=500, duration='2 days', available_slots=10,
        )
        self.date = timezone.now().date() + timedelta(days=3)

    def _make_pending_txn(self, with_cart=True):
        cart = Cart.objects.create(user=self.user, tour=self.tour, date=self.date, number_of_people=1)
        booking = Booking.objects.create(
            user=self.user, tour=self.tour, date=self.date,
            number_of_people=1, total_price=500, status='Pending',
        )
        txn = Transaction.objects.create(
            user=self.user, amount=500, payment_method='vnpay',
            status='Pending', cart_item_ids=[cart.id] if with_cart else [],
        )
        txn.bookings.add(booking)
        return txn, booking, cart

    def test_webhook_rejects_bad_signature(self):
        txn, _, _ = self._make_pending_txn()
        resp = self.client.post('/api/payments/webhook/', {
            'transaction_id': txn.id,
            'status': 'success',
            'signature': 'wrong-signature',
        })
        self.assertEqual(resp.status_code, 403)
        txn.refresh_from_db()
        self.assertEqual(txn.status, 'Pending')

    def test_webhook_success_marks_transaction_and_bookings_paid(self):
        txn, booking, cart = self._make_pending_txn()
        resp = self.client.post('/api/payments/webhook/', {
            'transaction_id': txn.id,
            'status': 'success',
            'signature': settings.PAYMENT_WEBHOOK_SECRET,
        })
        self.assertEqual(resp.status_code, 200)
        txn.refresh_from_db()
        booking.refresh_from_db()
        self.assertEqual(txn.status, 'Success')
        self.assertEqual(booking.status, 'Paid')
        self.assertFalse(Cart.objects.filter(id=cart.id).exists())

    def test_webhook_failure_keeps_booking_pending(self):
        txn, booking, cart = self._make_pending_txn()
        resp = self.client.post('/api/payments/webhook/', {
            'transaction_id': txn.id,
            'status': 'failed',
            'signature': settings.PAYMENT_WEBHOOK_SECRET,
        })
        self.assertEqual(resp.status_code, 200)
        txn.refresh_from_db()
        booking.refresh_from_db()
        self.assertEqual(txn.status, 'Failed')
        self.assertEqual(booking.status, 'Pending')
        self.assertTrue(Cart.objects.filter(id=cart.id).exists())

    def test_webhook_rejects_replay_after_success(self):
        txn, booking, cart = self._make_pending_txn()
        self.client.post('/api/payments/webhook/', {
            'transaction_id': txn.id,
            'status': 'success',
            'signature': settings.PAYMENT_WEBHOOK_SECRET,
        })
        # Gửi lại lần 2 - không được đổi trạng thái (chống replay)
        resp = self.client.post('/api/payments/webhook/', {
            'transaction_id': txn.id,
            'status': 'failed',
            'signature': settings.PAYMENT_WEBHOOK_SECRET,
        })
        self.assertEqual(resp.status_code, 200)
        txn.refresh_from_db()
        self.assertEqual(txn.status, 'Success')

    def test_webhook_unknown_transaction(self):
        resp = self.client.post('/api/payments/webhook/', {
            'transaction_id': 99999,
            'status': 'success',
            'signature': settings.PAYMENT_WEBHOOK_SECRET,
        })
        self.assertEqual(resp.status_code, 404)
