from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    AuditLogViewSet,
    ScholarEngagementViewSet,
    ComplianceReportViewSet,
    DashboardAnalyticsView,
)

app_name = 'analytics'

router = DefaultRouter()
router.register(r'audit-logs', AuditLogViewSet, basename='audit-logs')
router.register(r'engagement', ScholarEngagementViewSet, basename='engagement')
router.register(r'compliance/reports', ComplianceReportViewSet, basename='compliance-reports')

urlpatterns = [
    path('dashboard/', DashboardAnalyticsView.as_view(), name='dashboard-summary'),
    path('', include(router.urls)),
]
