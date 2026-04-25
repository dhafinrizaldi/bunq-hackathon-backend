from rest_framework.routers import DefaultRouter
from .views import AuthViewSet, MonetaryAccountViewSet

router = DefaultRouter()
router.register('auth', AuthViewSet, basename='auth')
router.register('monetary_accounts', MonetaryAccountViewSet, basename='monetary_accounts')

urlpatterns = router.urls
