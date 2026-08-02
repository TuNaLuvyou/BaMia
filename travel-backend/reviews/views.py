from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticatedOrReadOnly
from .models import Review
from .serializers import ReviewSerializer
from core.permissions import IsOwnerOrAdminOrReadOnly

class ReviewViewSet(viewsets.ModelViewSet):
    serializer_class = ReviewSerializer
    permission_classes = [IsAuthenticatedOrReadOnly, IsOwnerOrAdminOrReadOnly]

    def get_queryset(self):
        queryset = Review.objects.all()
        tour_id = self.request.query_params.get('tour')
        if tour_id:
            queryset = queryset.filter(tour_id=tour_id)
        return queryset

    def perform_create(self, serializer):
        # Tự động gán user đang đăng nhập cho review
        serializer.save(user=self.request.user)