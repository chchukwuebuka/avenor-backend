from django.urls import path
from .views import (
    CurrentTenantView,
    CurrentTenantBrandingView,
    CurrentTenantSettingsView,
)

urlpatterns = [
    path('current/', CurrentTenantView.as_view(), name='tenant-current'),
    path('current/branding/', CurrentTenantBrandingView.as_view(), name='tenant-current-branding'),
    path('current/settings/', CurrentTenantSettingsView.as_view(), name='tenant-current-settings'),
]
