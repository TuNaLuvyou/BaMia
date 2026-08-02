from django.test import TestCase

from chatbot.views import _extract_budget


class BudgetExtractionTests(TestCase):
    """Kiểm tra logic trích xuất ngân sách từ tin nhắn người dùng."""

    def test_full_number_format(self):
        self.assertEqual(_extract_budget("tour dưới 2000000 đồng"), 2000000)
        self.assertEqual(_extract_budget("khoảng 2.000.000"), 2000000)

    def test_trieu_format(self):
        self.assertEqual(_extract_budget("ngân sách 2 triệu"), 2000000)
        self.assertEqual(_extract_budget("khoảng 2,5 triệu"), 2500000)

    def test_nghin_format(self):
        self.assertEqual(_extract_budget("dưới 500k"), 500000)
        self.assertEqual(_extract_budget("tầm 300 nghìn"), 300000)

    def test_no_budget_returns_none(self):
        self.assertIsNone(_extract_budget("cho tôi xem tour Đà Lạt"))
        self.assertIsNone(_extract_budget("hello"))
