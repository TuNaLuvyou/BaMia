from django.contrib.auth.views import LoginView
from django.views import View
from django.views.generic import TemplateView, ListView, DeleteView, CreateView, UpdateView
from django.contrib.admin.views.decorators import staff_member_required
from django.utils.decorators import method_decorator
from django.contrib.auth.models import User
from django.db.models import Sum, Q
from django.db import transaction
from django.urls import reverse_lazy
from django.shortcuts import get_object_or_404, redirect
from django.contrib import messages
from django.core.mail import send_mail
from django.conf import settings
from django.utils.crypto import get_random_string
from django.http import JsonResponse
from django.core.files.base import ContentFile
import os

# Import models
from tours.models import Tour, Category, Destination
from bookings.models import Booking
from reviews.models import Review
from core.forms import TourForm, CategoryForm, DestinationForm
from users.models import SupportRequest

class CustomAdminLoginView(LoginView):
    template_name = 'custom_admin/login.html'
    redirect_authenticated_user = True

    def get_success_url(self):
        return '/admin/'

@method_decorator(staff_member_required(login_url='admin_login'), name='dispatch')
class CustomAdminDashboardView(TemplateView):
    template_name = 'custom_admin/dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['total_tours'] = Tour.objects.count()
        context['total_bookings'] = Booking.objects.count()
        context['total_users'] = User.objects.count()
        
        # Calculate revenue from 'Confirmed' or 'Paid' bookings
        # Assume total_price exists, but wait, does it? Booking has 'total_price'
        revenue = Booking.objects.filter(status__in=['Confirmed', 'Paid']).aggregate(Sum('total_price'))['total_price__sum']
        context['revenue'] = revenue if revenue else 0
        
        return context



@method_decorator(staff_member_required(login_url='admin_login'), name='dispatch')
class AdminTourListView(ListView):
    model = Tour
    template_name = 'custom_admin/tour_list.html'
    context_object_name = 'tours'
    
    def get_queryset(self):
        queryset = Tour.objects.all().order_by('-created_at')
        search_query = self.request.GET.get('q')
        category_id = self.request.GET.get('category')
        location_id = self.request.GET.get('location')

        if search_query:
            queryset = queryset.filter(Q(title__icontains=search_query) | Q(description__icontains=search_query))
        if category_id:
            queryset = queryset.filter(category_id=category_id)
        if location_id:
            queryset = queryset.filter(location_id=location_id)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['categories'] = Category.objects.all()
        context['locations'] = Destination.objects.all()
        return context

@method_decorator(staff_member_required(login_url='admin_login'), name='dispatch')
class AdminTourDeleteView(DeleteView):
    model = Tour
    success_url = reverse_lazy('admin_tours')
    # No template needed if we only POST to it

@method_decorator(staff_member_required(login_url='admin_login'), name='dispatch')
class AdminBookingListView(ListView):
    model = Booking
    template_name = 'custom_admin/booking_list.html'
    context_object_name = 'bookings'
    
    def get_queryset(self):
        queryset = Booking.objects.all().order_by('-created_at')
        search_query = self.request.GET.get('q')
        status = self.request.GET.get('status')

        if search_query:
            queryset = queryset.filter(
                Q(id__icontains=search_query) | 
                Q(user__username__icontains=search_query) | 
                Q(tour__title__icontains=search_query)
            )
        if status:
            queryset = queryset.filter(status=status)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['status_choices'] = Booking.STATUS_CHOICES
        return context

class AdminForgotPasswordView(View):
    def post(self, request):
        email = request.POST.get('email')
        if not email:
            messages.error(request, "Vui lòng nhập email.")
            return redirect('admin_login')
        
        try:
            user = User.objects.get(email=email)
            if not user.is_staff:
                messages.error(request, "Tài khoản này không có quyền truy cập quản trị.")
                return redirect('admin_login')

            # Reset password
            new_password = get_random_string(length=10)
            user.set_password(new_password)
            user.save()

            # Send Email
            subject = 'Khôi phục mật khẩu Admin TravelBaMia'
            message = f'Chào {user.username},\n\nMật khẩu Admin mới của bạn là: {new_password}\n\nVui lòng đăng nhập và đổi mật khẩu ngay.\n\nTrân trọng,\nSystem Admin'
            send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [email])

            # Create Support Request log (KHÔNG lưu mật khẩu vào database)
            SupportRequest.objects.create(
                user=user,
                request_type='FORGOT_PASSWORD',
                content=f"Quản trị viên yêu cầu cấp lại mật khẩu cho tài khoản staff: {user.username}. Mật khẩu mới đã được gửi về email.",
                status='PROCESSING'
            )

            messages.success(request, "Mật khẩu mới đã được gửi về email của bạn!")
            
        except User.DoesNotExist:
            messages.error(request, "Không tìm thấy tài khoản với email này.")
        except Exception:
            messages.error(request, "Đã có lỗi xảy ra khi gửi email. Vui lòng thử lại sau.")

        return redirect('admin_login')

    def get(self, request):
        return redirect('admin_login')

@method_decorator(staff_member_required(login_url='admin_login'), name='dispatch')
class AdminUserListView(ListView):
    model = User
    template_name = 'custom_admin/user_list.html'
    context_object_name = 'users_list'
    paginate_by = 10

    def get_queryset(self):
        queryset = User.objects.all().order_by('-date_joined')
        search = self.request.GET.get('search')
        role = self.request.GET.get('role')

        if search:
            queryset = queryset.filter(
                Q(username__icontains=search) | 
                Q(email__icontains=search)
            )
        
        if role == 'admin':
            queryset = queryset.filter(is_staff=True)
        elif role == 'customer':
            queryset = queryset.filter(is_staff=False)
            
        return queryset

@method_decorator(staff_member_required(login_url='admin_login'), name='dispatch')
class AdminUserUpdateView(UpdateView):
    model = User
    template_name = 'custom_admin/user_form.html'
    fields = ['username', 'email', 'is_staff', 'is_active']
    success_url = reverse_lazy('admin_users')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = f"Chỉnh sửa: {self.object.username}"
        return context

@method_decorator(staff_member_required(login_url='admin_login'), name='dispatch')
class AdminSupportRequestListView(ListView):
    model = SupportRequest
    template_name = 'custom_admin/request_list.html'
    context_object_name = 'requests'
    paginate_by = 10

    def get_queryset(self):
        queryset = SupportRequest.objects.all().order_by('-created_at')
        status_filter = self.request.GET.get('status')
        type_filter = self.request.GET.get('type')
        
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        if type_filter:
            queryset = queryset.filter(request_type=type_filter)
            
        return queryset

@staff_member_required(login_url='admin_login')
def admin_complete_support_request(request, pk):
    support_request = get_object_or_404(SupportRequest, pk=pk)
    support_request.status = 'COMPLETED'
    support_request.save()
    
    sender_name = support_request.user.username if support_request.user else support_request.guest_name
    messages.success(request, f"Đã hoàn thành yêu cầu của {sender_name}")
    return redirect('admin_requests')



@staff_member_required(login_url='admin_login')
def admin_toggle_user_status(request, user_id):
    user = get_object_or_404(User, id=user_id)
    
    if user == request.user:
        messages.error(request, "Bạn không thể tự khóa tài khoản của chính mình.")
        return redirect('admin_users')
        
    if user.is_superuser and not request.user.is_superuser:
        messages.error(request, "Bạn không có quyền thay đổi trạng thái của Superuser.")
        return redirect('admin_users')

    user.is_active = not user.is_active
    user.save()
    
    status = "mở khóa" if user.is_active else "khóa"
    messages.success(request, f"Đã {status} tài khoản {user.username} thành công.")
    
    return redirect('admin_users')

@staff_member_required(login_url='admin_login')
def admin_change_booking_status(request, pk):
    if request.method == 'POST':
        new_status = request.POST.get('status')
        valid_statuses = [choice[0] for choice in Booking.STATUS_CHOICES]
        if new_status in valid_statuses:
            with transaction.atomic():
                booking = get_object_or_404(Booking.objects.select_for_update(), pk=pk)
                old_status = booking.status

                if old_status != new_status:
                    if not booking.deleted_at:
                        tour = Tour.objects.select_for_update().get(id=booking.tour.id)
                        
                        if new_status == 'Cancelled' and old_status != 'Cancelled':
                            tour.available_slots += booking.number_of_people
                            tour.save(update_fields=['available_slots'])
                        elif old_status == 'Cancelled' and new_status != 'Cancelled':
                            if tour.available_slots < booking.number_of_people:
                                messages.error(request, f"Không thể đổi trạng thái. Tour chỉ còn {tour.available_slots} chỗ trống.")
                                return redirect('admin_bookings')
                            tour.available_slots -= booking.number_of_people
                            tour.save(update_fields=['available_slots'])

                    booking.status = new_status
                    booking.save(update_fields=['status'])
    return redirect('admin_bookings')

@method_decorator(staff_member_required(login_url='admin_login'), name='dispatch')
class AdminReviewListView(ListView):
    model = Review
    template_name = 'custom_admin/review_list.html'
    context_object_name = 'reviews'
    
    def get_queryset(self):
        queryset = Review.objects.all().order_by('-created_at')
        search_query = self.request.GET.get('q')
        rating = self.request.GET.get('rating')

        if search_query:
            queryset = queryset.filter(
                Q(user__username__icontains=search_query) | 
                Q(tour__title__icontains=search_query) |
                Q(comment__icontains=search_query)
            )
        if rating:
            queryset = queryset.filter(rating=rating)
        return queryset

@method_decorator(staff_member_required(login_url='admin_login'), name='dispatch')
class AdminReviewDeleteView(DeleteView):
    model = Review
    success_url = reverse_lazy('admin_reviews')



@method_decorator(staff_member_required(login_url='admin_login'), name='dispatch')
class AdminTourCreateView(CreateView):
    model = Tour
    form_class = TourForm
    template_name = 'custom_admin/tour_form.html'
    success_url = reverse_lazy('admin_tours')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = "Thêm mới Tour"
        return context

@method_decorator(staff_member_required(login_url='admin_login'), name='dispatch')
class AdminTourUpdateView(UpdateView):
    model = Tour
    form_class = TourForm
    template_name = 'custom_admin/tour_form.html'
    success_url = reverse_lazy('admin_tours')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = f"Chỉnh sửa: {self.object.title}"
        return context

# --- Category Management ---
@method_decorator(staff_member_required(login_url='admin_login'), name='dispatch')
class AdminCategoryListView(ListView):
    model = Category
    template_name = 'custom_admin/category_list.html'
    context_object_name = 'categories'

    def get_queryset(self):
        queryset = Category.objects.all().order_by('name')
        search_query = self.request.GET.get('q')
        if search_query:
            queryset = queryset.filter(name__icontains=search_query)
        return queryset

@method_decorator(staff_member_required(login_url='admin_login'), name='dispatch')
class AdminCategoryCreateView(CreateView):
    model = Category
    form_class = CategoryForm
    template_name = 'custom_admin/category_form.html'
    success_url = reverse_lazy('admin_categories')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = "Thêm mới Danh mục"
        return context

@method_decorator(staff_member_required(login_url='admin_login'), name='dispatch')
class AdminCategoryUpdateView(UpdateView):
    model = Category
    form_class = CategoryForm
    template_name = 'custom_admin/category_form.html'
    success_url = reverse_lazy('admin_categories')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = f"Chỉnh sửa Danh mục: {self.object.name}"
        return context

@method_decorator(staff_member_required(login_url='admin_login'), name='dispatch')
class AdminCategoryDeleteView(DeleteView):
    model = Category
    success_url = reverse_lazy('admin_categories')

# --- Destination Management ---
@method_decorator(staff_member_required(login_url='admin_login'), name='dispatch')
class AdminDestinationListView(ListView):
    model = Destination
    template_name = 'custom_admin/destination_list.html'
    context_object_name = 'destinations'

    def get_queryset(self):
        queryset = Destination.objects.all().order_by('name')
        search_query = self.request.GET.get('q')
        if search_query:
            queryset = queryset.filter(Q(name__icontains=search_query) | Q(description__icontains=search_query))
        return queryset

@method_decorator(staff_member_required(login_url='admin_login'), name='dispatch')
class AdminDestinationCreateView(CreateView):
    model = Destination
    form_class = DestinationForm
    template_name = 'custom_admin/destination_form.html'
    success_url = reverse_lazy('admin_destinations')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = "Thêm mới Địa điểm"
        return context

@method_decorator(staff_member_required(login_url='admin_login'), name='dispatch')
class AdminDestinationUpdateView(UpdateView):
    model = Destination
    form_class = DestinationForm
    template_name = 'custom_admin/destination_form.html'
    success_url = reverse_lazy('admin_destinations')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = f"Chỉnh sửa Địa điểm: {self.object.name}"
        return context

@method_decorator(staff_member_required(login_url='admin_login'), name='dispatch')
class AdminDestinationDeleteView(DeleteView):
    model = Destination
    success_url = reverse_lazy('admin_destinations')

@staff_member_required(login_url='admin_login')
def admin_get_destination_info(request, pk):
    """Lấy nội dung file text và keywords của địa điểm"""
    dest = get_object_or_404(Destination, pk=pk)
    content = ""
    if dest.info_file:
        try:
            with open(dest.info_file.path, 'r', encoding='utf-8') as f:
                content = f.read()
        except Exception as e:
            content = f"Lỗi đọc file: {str(e)}"
    return JsonResponse({
        'content': content,
        'keywords': dest.keywords or ""
    })

@staff_member_required(login_url='admin_login')
def admin_update_destination_info(request, pk):
    """Cập nhật nội dung file text và keywords của địa điểm"""
    if request.method == 'POST':
        dest = get_object_or_404(Destination, pk=pk)
        content = request.POST.get('content', '')
        keywords = request.POST.get('keywords', '')
        
        dest.keywords = keywords
        dest.save()
        
        # Xử lý file
        file_name = f"info_{dest.id}.txt"
        
        # Nếu đã có file, ghi đè. Nếu chưa, tạo mới.
        if dest.info_file:
            try:
                with open(dest.info_file.path, 'w', encoding='utf-8') as f:
                    f.write(content)
            except Exception as e:
                return JsonResponse({'error': str(e)}, status=500)
        else:
            # Tạo file mới thông qua FileField
            dest.info_file.save(file_name, ContentFile(content.encode('utf-8')))

        return JsonResponse({'status': 'success'})
    return JsonResponse({'error': 'Method not allowed'}, status=405)
