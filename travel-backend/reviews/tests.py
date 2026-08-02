from django.test import TestCase
from django.contrib.auth.models import User
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from tours.models import Destination, Tour
from reviews.models import Review


def auth_headers(user):
    refresh = RefreshToken.for_user(user)
    return {'HTTP_AUTHORIZATION': f'Bearer {refresh.access_token}'}


class ReviewRatingSyncTests(TestCase):
    """Kiểm tra signal tự động đồng bộ Tour.rating khi review thay đổi."""

    def setUp(self):
        self.user = User.objects.create_user(username='reviewer', password='StrongPass123!')
        self.other = User.objects.create_user(username='otheruser', password='StrongPass123!')
        self.client = APIClient()
        dest = Destination.objects.create(name='Đà Nẵng', description='Thành phố biển')
        self.tour = Tour.objects.create(
            title='Tour Đà Nẵng', description='desc', location=dest,
            price=500, duration='2 days', available_slots=10,
        )

    def test_create_review_updates_rating(self):
        resp = self.client.post(
            '/api/reviews/',
            {'tour': self.tour.id, 'rating': 4, 'comment': 'Rất tốt'},
            **auth_headers(self.user),
        )
        self.assertEqual(resp.status_code, 201)
        self.tour.refresh_from_db()
        self.assertEqual(self.tour.rating, 4.0)

    def test_multiple_reviews_calculate_average(self):
        Review.objects.create(user=self.user, tour=self.tour, rating=5, comment='a')
        Review.objects.create(user=self.other, tour=self.tour, rating=3, comment='b')
        self.tour.refresh_from_db()
        self.assertEqual(self.tour.rating, 4.0)

    def test_delete_review_recalculates_rating(self):
        r1 = Review.objects.create(user=self.user, tour=self.tour, rating=5, comment='a')
        Review.objects.create(user=self.other, tour=self.tour, rating=3, comment='b')

        resp = self.client.delete(f'/api/reviews/{r1.id}/', **auth_headers(self.user))
        self.assertEqual(resp.status_code, 204)
        self.tour.refresh_from_db()
        self.assertEqual(self.tour.rating, 3.0)

    def test_delete_last_review_resets_rating_to_zero(self):
        review = Review.objects.create(user=self.user, tour=self.tour, rating=5, comment='a')

        resp = self.client.delete(f'/api/reviews/{review.id}/', **auth_headers(self.user))
        self.assertEqual(resp.status_code, 204)
        self.tour.refresh_from_db()
        self.assertEqual(self.tour.rating, 0.0)


class ReviewPermissionTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='reviewer', password='StrongPass123!')
        self.other = User.objects.create_user(username='otheruser', password='StrongPass123!')
        self.client = APIClient()
        dest = Destination.objects.create(name='Hạ Long', description='Vịnh')
        self.tour = Tour.objects.create(
            title='Tour Hạ Long', description='desc', location=dest,
            price=600, duration='2 days', available_slots=10,
        )

    def test_anonymous_cannot_create_review(self):
        resp = self.client.post('/api/reviews/', {'tour': self.tour.id, 'rating': 5, 'comment': 'x'})
        self.assertEqual(resp.status_code, 401)

    def test_owner_cannot_delete_others_review(self):
        review = Review.objects.create(user=self.other, tour=self.tour, rating=5, comment='a')
        resp = self.client.delete(f'/api/reviews/{review.id}/', **auth_headers(self.user))
        self.assertEqual(resp.status_code, 403)

    def test_list_reviews_is_public(self):
        Review.objects.create(user=self.other, tour=self.tour, rating=5, comment='a')
        resp = self.client.get('/api/reviews/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data), 1)

    def test_review_user_is_auto_assigned(self):
        resp = self.client.post(
            '/api/reviews/',
            {'tour': self.tour.id, 'rating': 5, 'comment': 'Tuyệt'},
            **auth_headers(self.user),
        )
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.data['user'], self.user.id)
