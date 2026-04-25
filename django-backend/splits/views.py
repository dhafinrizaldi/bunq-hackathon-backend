from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from .models import SplitSession
from .serializers import SplitSessionDetailSerializer, SplitSessionListSerializer


class SplitSessionViewSet(viewsets.ModelViewSet):
    queryset = SplitSession.objects.select_related('transaction').prefetch_related(
        'participants', 'items', 'payment_requests'
    )
    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return SplitSessionDetailSerializer
        return SplitSessionListSerializer
