from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import SplitSessionViewSet, TransactionViewSet

router = DefaultRouter()
# Register transactions BEFORE the catch-all `r''` SplitSession route so the
# router resolves /api/splits/transactions/ correctly.
router.register(r'transactions', TransactionViewSet, basename='transaction')
router.register(r'', SplitSessionViewSet, basename='split-session')

urlpatterns = [
    path('', include(router.urls)),
]
