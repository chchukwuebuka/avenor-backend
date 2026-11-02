from django.urls import path
from .views import (
    CurrentTenantView,
    CurrentTenantBrandingView,
    CurrentTenantSettingsView,
    TenantFleetListCreateView,
    TenantFleetDetailView,
    TenantFleetDomainsView,
    TenantDomainVerifyView,
    TenantFleetBrandingView,
    TenantFleetSettingsView,
    PlatformFleetStatsView,
)

urlpatterns = [
    # Tenant resolution endpoints (Institutional Frontend Apps)
    path('current/', CurrentTenantView.as_view(), name='tenant-current'),
    path('current/branding/', CurrentTenantBrandingView.as_view(), name='tenant-current-branding'),
    path('current/settings/', CurrentTenantSettingsView.as_view(), name='tenant-current-settings'),
    path('branding/', CurrentTenantBrandingView.as_view(), name='tenant-branding-legacy'),
    path('settings/', CurrentTenantSettingsView.as_view(), name='tenant-settings-legacy'),

    # Fleet Management endpoints (Avenor Control Platform Console)
    path('', TenantFleetListCreateView.as_view(), name='tenant-fleet-list-create'),
    path('stats/', PlatformFleetStatsView.as_view(), name='platform-fleet-stats'),
    path('<uuid:pk>/', TenantFleetDetailView.as_view(), name='tenant-fleet-detail'),
    path('<uuid:pk>/domains/', TenantFleetDomainsView.as_view(), name='tenant-fleet-domains'),
    path('domains/<uuid:pk>/verify/', TenantDomainVerifyView.as_view(), name='tenant-domain-verify'),
    path('<uuid:pk>/branding/', TenantFleetBrandingView.as_view(), name='tenant-fleet-branding'),
    path('<uuid:pk>/settings/', TenantFleetSettingsView.as_view(), name='tenant-fleet-settings'),
]
