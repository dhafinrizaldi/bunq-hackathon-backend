from rest_framework.routers import DefaultRouter

from .views import AuthViewSet, ContactsViewSet, MeViewSet, MonetaryAccountViewSet

router = DefaultRouter()
router.register('auth', AuthViewSet, basename='auth')
router.register('monetary_accounts', MonetaryAccountViewSet, basename='monetary_accounts')
router.register('contacts', ContactsViewSet, basename='contacts')
router.register('me', MeViewSet, basename='me')

urlpatterns = router.urls
