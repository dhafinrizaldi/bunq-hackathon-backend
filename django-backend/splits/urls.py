from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import SplitSessionViewSet

router = DefaultRouter()
router.register(r'', SplitSessionViewSet, basename='split-session')

urlpatterns = [
    path('', include(router.urls)),
]
