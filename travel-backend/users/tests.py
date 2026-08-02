from django.test import TestCase
from django.contrib.auth.models import User
from django.core import mail
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes
from django.contrib.auth.tokens import default_token_generator
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken


def auth_headers(user):
    refresh = RefreshToken.for_user(user)
    return {'HTTP_AUTHORIZATION': f'Bearer {refresh.access_token}'}


class RegisterTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_register_success(self):
        resp = self.client.post('/api/auth/register/', {
            'username': 'newuser',
            'email': 'new@example.com',
            'password': 'StrongPass123!',
        })
        self.assertEqual(resp.status_code, 201)
        self.assertTrue(User.objects.filter(username='newuser').exists())

    def test_register_duplicate_username_rejected(self):
        User.objects.create_user(username='taken', email='a@example.com', password='StrongPass123!')
        resp = self.client.post('/api/auth/register/', {
            'username': 'taken',
            'email': 'b@example.com',
            'password': 'StrongPass123!',
        })
        self.assertEqual(resp.status_code, 400)


class LoginTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='loginuser', email='l@example.com', password='StrongPass123!'
        )

    def test_login_success_returns_tokens(self):
        resp = self.client.post('/api/auth/login/', {
            'username': 'loginuser',
            'password': 'StrongPass123!',
        })
        self.assertEqual(resp.status_code, 200)
        self.assertIn('access', resp.data)
        self.assertIn('refresh', resp.data)

    def test_login_wrong_password_rejected(self):
        resp = self.client.post('/api/auth/login/', {
            'username': 'loginuser',
            'password': 'wrongpassword',
        })
        self.assertEqual(resp.status_code, 401)


class ForgotPasswordTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_forgot_password_existing_email_sends_email(self):
        User.objects.create_user(username='fuser', email='forgot@example.com', password='StrongPass123!')
        resp = self.client.post('/api/auth/forgot-password/', {'email': 'forgot@example.com'})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('reset-password', mail.outbox[0].body)

    def test_forgot_password_unknown_email_no_enumeration(self):
        """Không được tiết lộ email có tồn tại hay không (chống user enumeration)."""
        resp = self.client.post('/api/auth/forgot-password/', {'email': 'nobody@example.com'})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(mail.outbox), 0)


class ResetPasswordTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='ruser', email='reset@example.com', password='OldPass123!'
        )
        self.token = default_token_generator.make_token(self.user)
        self.uid = urlsafe_base64_encode(force_bytes(self.user.pk))

    def test_reset_password_valid_token(self):
        resp = self.client.post('/api/auth/reset-password-confirm/', {
            'uid': self.uid,
            'token': self.token,
            'new_password': 'NewPass456!',
        })
        self.assertEqual(resp.status_code, 200)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('NewPass456!'))

    def test_reset_password_invalid_token_rejected(self):
        resp = self.client.post('/api/auth/reset-password-confirm/', {
            'uid': self.uid,
            'token': 'invalid-token',
            'new_password': 'NewPass456!',
        })
        self.assertEqual(resp.status_code, 400)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('OldPass123!'))

    def test_reset_link_validation_get(self):
        resp = self.client.get(f'/api/auth/reset-password-confirm/?uid={self.uid}&token={self.token}')
        self.assertEqual(resp.status_code, 200)

    def test_reset_link_validation_invalid(self):
        resp = self.client.get('/api/auth/reset-password-confirm/?uid=bad&token=bad')
        self.assertEqual(resp.status_code, 400)


class AuthenticatedUserTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='cpuser', email='cp@example.com', password='OldPass123!'
        )

    def test_change_password(self):
        self.client.credentials(**auth_headers(self.user))
        resp = self.client.post('/api/auth/change-password/', {
            'old_password': 'OldPass123!',
            'new_password': 'NewPass456!',
        })
        self.assertEqual(resp.status_code, 200)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('NewPass456!'))

    def test_change_password_wrong_old_password(self):
        self.client.credentials(**auth_headers(self.user))
        resp = self.client.post('/api/auth/change-password/', {
            'old_password': 'wrong-old',
            'new_password': 'NewPass456!',
        })
        self.assertEqual(resp.status_code, 400)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('OldPass123!'))

    def test_change_password_requires_auth(self):
        resp = self.client.post('/api/auth/change-password/', {
            'old_password': 'OldPass123!',
            'new_password': 'NewPass456!',
        })
        self.assertEqual(resp.status_code, 401)

    def test_profile_update_phone(self):
        self.client.credentials(**auth_headers(self.user))
        resp = self.client.patch('/api/auth/profile/', {'phone': '0901234567'})
        self.assertEqual(resp.status_code, 200)
        self.user.profile.refresh_from_db()
        self.assertEqual(self.user.profile.phone, '0901234567')
