from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import (
    PaymentViewSet,
    RequestInquiryViewSet,
    AuthViewSet,
    MonetaryAccountViewSet,
    bunq_webhook,
    contacts_internal,
    contacts_view,
    execute_allocation,
    salary_setup_view,
    simulate_salary,
    agent_query
)

router = DefaultRouter()
router.register('auth', AuthViewSet, basename='auth')
router.register('monetary_accounts', MonetaryAccountViewSet, basename='monetary_accounts')
router.register('payment', PaymentViewSet, basename='payment')
router.register('request-inquiry', RequestInquiryViewSet, basename='request-inquiry')

urlpatterns = router.urls + [
    path('salary-setup/', salary_setup_view, name='salary-setup'),
    path('contacts/', contacts_view, name='contacts'),
    path('contacts/internal/', contacts_internal, name='contacts-internal'),
    path('webhook/bunq/', bunq_webhook, name='bunq-webhook'),
    path('simulate-salary/', simulate_salary, name='simulate-salary'),
    path('execute-allocation/', execute_allocation, name='execute-allocation'),
    path('query/', agent_query, name='agent-query'),
]
