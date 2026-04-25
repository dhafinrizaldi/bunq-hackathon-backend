from rest_framework.routers import DefaultRouter
from .views import AuthViewSet, MonetaryAccountViewSet, PaymentViewSet

router = DefaultRouter()
router.register('auth', AuthViewSet, basename='auth')
router.register('monetary_accounts', MonetaryAccountViewSet, basename='monetary_accounts')
router.register('payments', PaymentViewSet, basename='payments')

urlpatterns = router.urls
