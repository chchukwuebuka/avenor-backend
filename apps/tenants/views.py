from rest_framework import generics, permissions, status
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, OpenApiResponse
from .models import Tenant, TenantBranding, TenantSettings, TenantDomain
from .serializers import (
    TenantPublicSerializer,
    TenantBrandingSerializer,
    TenantSettingsSerializer,
    TenantDomainSerializer,
)

@extend_schema(
    summary='Retrieve Current Resolved Tenant',
    description='Returns the active tenant, verified domains, branding tokens, and settings resolved from the incoming domain.',
    responses={
        200: TenantPublicSerializer,
        404: OpenApiResponse(description='Tenant not resolved for this domain'),
    }
)
class CurrentTenantView(generics.GenericAPIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request, *args, **kwargs):
        tenant = getattr(request, 'tenant', None)
        if not tenant:
            return Response(
                {
                    'success': False,
                    'message': 'No institution found for the requested domain.',
                    'errors': {'domain': ['Domain is not associated with an active tenant.']},
                },
                status=status.HTTP_404_NOT_FOUND
            )
        serializer = TenantPublicSerializer(tenant)
        return Response({
            'success': True,
            'data': serializer.data
        })

@extend_schema(
    summary='Retrieve or Update Current Tenant Branding',
    description='Returns white-label branding tokens (logo, colours, typography, footer).',
    responses={200: TenantBrandingSerializer}
)
class CurrentTenantBrandingView(generics.GenericAPIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request, *args, **kwargs):
        tenant = getattr(request, 'tenant', None)
        if not tenant:
            return Response(
                {'success': False, 'message': 'Tenant not resolved.', 'errors': {}},
                status=status.HTTP_404_NOT_FOUND
            )
        branding, _ = TenantBranding.objects.get_or_create(
            tenant=tenant,
            defaults={'site_name': tenant.name, 'support_email': tenant.contact_email}
        )
        serializer = TenantBrandingSerializer(branding)
        return Response({
            'success': True,
            'data': serializer.data
        })

@extend_schema(
    summary='Retrieve or Update Current Tenant Settings',
    description='Returns institution feature flags (registration, applications, catalogues).',
    responses={200: TenantSettingsSerializer}
)
class CurrentTenantSettingsView(generics.GenericAPIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request, *args, **kwargs):
        tenant = getattr(request, 'tenant', None)
        if not tenant:
            return Response(
                {'success': False, 'message': 'Tenant not resolved.', 'errors': {}},
                status=status.HTTP_404_NOT_FOUND
            )
        tenant_settings, _ = TenantSettings.objects.get_or_create(tenant=tenant)
        serializer = TenantSettingsSerializer(tenant_settings)
        return Response({
            'success': True,
            'data': serializer.data
        })
