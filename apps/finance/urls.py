from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    SubscriptionPlanViewSet,
    TenantSubscriptionViewSet,
    InvoiceViewSet,
    TransactionViewSet,
    UnifiedWebhookView,
)

app_name = 'finance'

router = DefaultRouter()
router.register(r'plans', SubscriptionPlanViewSet, basename='plans')
router.register(r'subscription', TenantSubscriptionViewSet, basename='subscription')
router.register(r'invoices', InvoiceViewSet, basename='invoices')
router.register(r'transactions', TransactionViewSet, basename='transactions')

urlpatterns = [
    path('webhook/', UnifiedWebhookView.as_view(), name='unified-webhook'),
    path('', include(router.urls)),
]
