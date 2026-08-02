import logging

from rest_framework import generics
from django.contrib.auth.models import User
from .serializers import RegisterSerializer, SupportRequestSerializer, UserUpdateSerializer, ChangePasswordSerializer
from rest_framework.permissions import AllowAny, IsAuthenticated

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.core.mail import send_mail
from django.conf import settings
from .models import SupportRequest

logger = logging.getLogger(__name__)

# Thư viện bảo mật tích hợp sẵn của Django phục vụ việc tạo Token và mã hóa UID
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str

class RegisterView(generics.CreateAPIView):
    queryset = User.objects.all()
    permission_classes = (AllowAny,)
    serializer_class = RegisterSerializer

class ForgotPasswordView(APIView):
    permission_classes = (AllowAny,)

    def post(self, request):
        email = request.data.get('email')
        if not email:
            return Response({"error": "Vui lòng nhập email"}, status=status.HTTP_400_BAD_REQUEST)
        
        # Không tiết lộ email có tồn tại hay không (chống dò email / user enumeration)
        try:
            user = User.objects.get(email=email)

            # Sử dụng thư viện của Django để tạo Token bảo mật một lần và mã hóa ID người dùng (UID)
            token = default_token_generator.make_token(user)
            uid = urlsafe_base64_encode(force_bytes(user.pk))

            # Tạo đường dẫn trỏ về trang Reset Password của Frontend
            # Mặc định React FE chạy cổng 5173
            frontend_url = getattr(settings, 'FRONTEND_URL', 'http://localhost:5173')
            reset_link = f"{frontend_url}/reset-password/{uid}/{token}"

            # Gửi email chứa đường dẫn đặt lại mật khẩu
            subject = 'Khôi phục mật khẩu TravelBaMia'
            message = (
                f'Chào {user.username},\n\n'
                f'Bạn nhận được email này vì đã yêu cầu khôi phục mật khẩu cho tài khoản tại TravelBaMia.\n'
                f'Vui lòng nhấn vào đường dẫn dưới đây để tiến hành đặt mật khẩu mới:\n\n'
                f'{reset_link}\n\n'
                f'Lưu ý: Liên kết này chỉ có hiệu lực sử dụng một lần và sẽ hết hạn sau một khoảng thời gian nhất định.\n'
                f'Nếu bạn không yêu cầu thay đổi mật khẩu, vui lòng bỏ qua email này.\n\n'
                f'Trân trọng,\nĐội ngũ TravelBaMia'
            )
            send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [email])
        except User.DoesNotExist:
            pass  # Không báo lỗi để tránh lộ thông tin
        except Exception:
            # Log lỗi nội bộ nhưng không lộ ra ngoài
            logger.exception("ForgotPassword failed")
            return Response({"error": "Đã có lỗi xảy ra. Vui lòng thử lại sau."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        return Response({"success": "Nếu email tồn tại trong hệ thống, liên kết đặt lại mật khẩu đã được gửi về email của bạn!"}, status=status.HTTP_200_OK)

class ResetPasswordConfirmView(APIView):
    permission_classes = (AllowAny,)

    def get(self, request):
        # API GET dùng để xác thực nhanh xem liên kết Token có còn hợp lệ hay không khi trang vừa load
        uidb64 = request.query_params.get('uid')
        token = request.query_params.get('token')

        if not uidb64 or not token:
            return Response({"error": "Thiếu thông tin xác thực"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            uid = force_str(urlsafe_base64_decode(uidb64))
            user = User.objects.get(pk=uid)
        except (TypeError, ValueError, OverflowError, User.DoesNotExist):
            return Response({"error": "Liên kết không hợp lệ"}, status=status.HTTP_400_BAD_REQUEST)

        if not default_token_generator.check_token(user, token):
            return Response({"error": "Liên kết khôi phục mật khẩu đã hết hạn hoặc đã được sử dụng!"}, status=status.HTTP_400_BAD_REQUEST)

        return Response({"success": "Liên kết hợp lệ"}, status=status.HTTP_200_OK)

    def post(self, request):
        uidb64 = request.data.get('uid')
        token = request.data.get('token')
        new_password = request.data.get('new_password')

        if not uidb64 or not token or not new_password:
            return Response({"error": "Thiếu thông tin bắt buộc"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            # Giải mã mã hóa UID để lấy ID của User
            uid = force_str(urlsafe_base64_decode(uidb64))
            user = User.objects.get(pk=uid)
        except (TypeError, ValueError, OverflowError, User.DoesNotExist):
            return Response({"error": "Đường dẫn không hợp lệ hoặc người dùng không tồn tại"}, status=status.HTTP_400_BAD_REQUEST)

        # Xác thực Token của Django xem có khớp và có còn hạn hay không
        if not default_token_generator.check_token(user, token):
            return Response({"error": "Liên kết khôi phục mật khẩu đã hết hạn hoặc đã được sử dụng!"}, status=status.HTTP_400_BAD_REQUEST)

        # Lưu mật khẩu mới và lưu vào database
        user.set_password(new_password)
        user.save()
        
        return Response({"success": "Mật khẩu đã được đặt lại thành công!"}, status=status.HTTP_200_OK)

class SupportRequestCreateView(generics.CreateAPIView):
    queryset = SupportRequest.objects.all()
    serializer_class = SupportRequestSerializer
    permission_classes = (AllowAny,)

    def perform_create(self, serializer):
        if self.request.user.is_authenticated:
            serializer.save(user=self.request.user)
        else:
            serializer.save()

class UserProfileView(generics.RetrieveUpdateAPIView):
    serializer_class = UserUpdateSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        return self.request.user

class ChangePasswordView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            user = request.user
            user.set_password(serializer.validated_data['new_password'])
            user.save()
            return Response({"success": "Đổi mật khẩu thành công!"}, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)