from rest_framework import viewsets, filters
from django_filters.rest_framework import DjangoFilterBackend

from .models import Tour, Destination, Category
from .serializers import TourSerializer, DestinationSerializer, CategorySerializer
from core.permissions import IsAdminUserOrReadOnly


class CategoryViewSet(viewsets.ModelViewSet):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    permission_classes = [IsAdminUserOrReadOnly]


class DestinationViewSet(viewsets.ModelViewSet):
    queryset = Destination.objects.all()
    serializer_class = DestinationSerializer
    permission_classes = [IsAdminUserOrReadOnly]


class TourViewSet(viewsets.ModelViewSet):
    queryset = Tour.objects.all()
    serializer_class = TourSerializer
    permission_classes = [IsAdminUserOrReadOnly]

    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['location', 'duration']
    search_fields = ['title', 'description']
    ordering_fields = ['price', 'rating', 'created_at']
