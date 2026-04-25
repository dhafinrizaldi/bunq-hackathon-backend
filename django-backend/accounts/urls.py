from rest_framework.routers import DefaultRouter
from .views import AuthViewSet, MonetaryAccountViewSet, PaymentViewSet, RequestInquiryViewSet

router = DefaultRouter()
router.register('auth', AuthViewSet, basename='auth')
router.register('monetary_accounts', MonetaryAccountViewSet, basename='monetary_accounts')
router.register('payment', PaymentViewSet, basename='payment')
router.register('request-inquiry', RequestInquiryViewSet, basename='request-inquiry')

urlpatterns = router.urls
