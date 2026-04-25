from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import (
    AuthViewSet,
    MonetaryAccountViewSet,
    bunq_webhook,
    contacts_internal,
    contacts_view,
    execute_allocation,
    salary_setup_view,
    simulate_salary,
)

router = DefaultRouter()
router.register('auth', AuthViewSet, basename='auth')
router.register('monetary_accounts', MonetaryAccountViewSet, basename='monetary_accounts')

urlpatterns = router.urls + [
    path('salary-setup/', salary_setup_view, name='salary-setup'),
    path('contacts/', contacts_view, name='contacts'),
    path('contacts/internal/', contacts_internal, name='contacts-internal'),
    path('webhook/bunq/', bunq_webhook, name='bunq-webhook'),
    path('simulate-salary/', simulate_salary, name='simulate-salary'),
    path('execute-allocation/', execute_allocation, name='execute-allocation'),
]
