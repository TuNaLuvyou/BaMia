from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import RedirectView
from django.contrib.auth.views import LogoutView
from rest_framework.routers import DefaultRouter

from tours.views import TourViewSet, DestinationViewSet, CategoryViewSet
from chatbot.views import ChatbotAPIView, ChatbotFeedbackView, OllamaHealthView
from bookings.views import BookingViewSet, CartViewSet, MyItineraryView, AdminDashboardView
from reviews.views import ReviewViewSet
from core.views import (
    CustomAdminLoginView, CustomAdminDashboardView, AdminTourListView, AdminTourDeleteView,
    AdminTourCreateView, AdminTourUpdateView,
    AdminCategoryListView, AdminCategoryCreateView, AdminCategoryUpdateView, AdminCategoryDeleteView,
    AdminDestinationListView, AdminDestinationCreateView, AdminDestinationUpdateView, AdminDestinationDeleteView,
    AdminBookingListView, admin_change_booking_status, AdminReviewListView, AdminReviewDeleteView,
    AdminForgotPasswordView, AdminUserListView, AdminUserUpdateView, AdminSupportRequestListView, admin_complete_support_request, admin_toggle_user_status,
    admin_get_destination_info, admin_update_destination_info
)

# Khởi tạo Router tự động sinh API endpoint
router = DefaultRouter()
router.register(r'categories', CategoryViewSet, basename='category')
router.register(r'tours', TourViewSet, basename='tour')
router.register(r'cart', CartViewSet, basename='cart')
router.register(r'destinations', DestinationViewSet, basename='destination')
router.register(r'bookings', BookingViewSet, basename='booking')
router.register(r'reviews', ReviewViewSet, basename='review')

urlpatterns = [
    path('', RedirectView.as_view(url='/api/', permanent=False)),
    path('admin/login/', CustomAdminLoginView.as_view(), name='admin_login'),
    path('admin/forgot-password/', AdminForgotPasswordView.as_view(), name='admin_forgot_password'),
    path('admin/logout/', LogoutView.as_view(next_page='admin_login'), name='admin_logout'),
    path('admin/', CustomAdminDashboardView.as_view(), name='custom_admin_dashboard'),
    
    # Custom Admin CRUD routes
    path('admin/tours/', AdminTourListView.as_view(), name='admin_tours'),
    path('admin/tours/add/', AdminTourCreateView.as_view(), name='admin_tour_create'),
    path('admin/tours/<int:pk>/edit/', AdminTourUpdateView.as_view(), name='admin_tour_edit'),
    path('admin/tours/<int:pk>/delete/', AdminTourDeleteView.as_view(), name='admin_tour_delete'),
    
    path('admin/categories/', AdminCategoryListView.as_view(), name='admin_categories'),
    path('admin/categories/add/', AdminCategoryCreateView.as_view(), name='admin_category_create'),
    path('admin/categories/<int:pk>/edit/', AdminCategoryUpdateView.as_view(), name='admin_category_edit'),
    path('admin/categories/<int:pk>/delete/', AdminCategoryDeleteView.as_view(), name='admin_category_delete'),

    path('admin/destinations/', AdminDestinationListView.as_view(), name='admin_destinations'),
    path('admin/destinations/add/', AdminDestinationCreateView.as_view(), name='admin_destination_create'),
    path('admin/destinations/<int:pk>/edit/', AdminDestinationUpdateView.as_view(), name='admin_destination_edit'),
    path('admin/destinations/<int:pk>/delete/', AdminDestinationDeleteView.as_view(), name='admin_destination_delete'),
    path('admin/destinations/<int:pk>/get-info/', admin_get_destination_info, name='admin_destination_get_info'),
    path('admin/destinations/<int:pk>/update-info/', admin_update_destination_info, name='admin_destination_update_info'),
    
    path('admin/bookings/', AdminBookingListView.as_view(), name='admin_bookings'),
    path('admin/bookings/<int:pk>/status/', admin_change_booking_status, name='admin_change_booking_status'),
    
    path('admin/reviews/', AdminReviewListView.as_view(), name='admin_reviews'),
    path('admin/reviews/<int:pk>/delete/', AdminReviewDeleteView.as_view(), name='admin_review_delete'),
    
    path('admin/users/', AdminUserListView.as_view(), name='admin_users'),
    path('admin/users/<int:pk>/edit/', AdminUserUpdateView.as_view(), name='admin_user_edit'),
    path('admin/users/<int:user_id>/toggle-status/', admin_toggle_user_status, name='admin_toggle_user_status'),
    
    path('admin/requests/', AdminSupportRequestListView.as_view(), name='admin_requests'),
    path('admin/requests/<int:pk>/complete/', admin_complete_support_request, name='admin_complete_support_request'),
    
    path('api/auth/', include('users.urls')), # Chuyển đăng ký/đăng nhập vào group auth/
    path('api/chat/', ChatbotAPIView.as_view(), name='ai-chat'),
    path('api/chat/health/', OllamaHealthView.as_view(), name='ai-health'),
    path('api/chat/feedback/', ChatbotFeedbackView.as_view(), name='ai-chat-feedback'),
    path('api/', include(router.urls)),       # Toàn bộ API CRUD sẽ nằm ở đây
    path('api/my-itinerary/', MyItineraryView.as_view(), name='my-itinerary'),
    path('api/admin-dashboard/', AdminDashboardView.as_view(), name='admin-dashboard'),
    path('api/payments/', include('payments.urls')),
]

# Phục vụ file media (ảnh upload) trong môi trường development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)