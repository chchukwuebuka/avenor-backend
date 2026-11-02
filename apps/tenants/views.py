from rest_framework import generics, permissions, status, views
from rest_framework.response import Response
from django.db import transaction, models
from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.utils import extend_schema, OpenApiResponse
from common.permissions import IsPlatformOwner
from .models import Tenant, TenantBranding, TenantSettings, TenantDomain, TenantStatus
from .serializers import (
    TenantPublicSerializer,
    TenantAdminSerializer,
    TenantProvisionSerializer,
    TenantBrandingSerializer,
    TenantSettingsSerializer,
    TenantDomainSerializer,
    CreateTenantDomainSerializer,
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
    summary='Retrieve Current Tenant Branding',
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
    summary='Retrieve Current Tenant Settings',
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


# =========================================================================
# PLATFORM OPERATOR FLEET APIS (AVENOR CONTROL)
# =========================================================================

class TenantFleetListCreateView(views.APIView):
    """
    List all institutions or provision a new institution tenant atomically.
    Restricted to Platform Owners and Platform Staff.
    """
    permission_classes = [IsPlatformOwner]

    def get(self, request):
        qs = Tenant.objects.all().prefetch_related('domains', 'branding', 'settings').order_by('-created_at')

        status_param = request.query_params.get('status')
        if status_param:
            qs = qs.filter(status=status_param)

        type_param = request.query_params.get('type')
        if type_param:
            qs = qs.filter(institution_type=type_param)

        search = request.query_params.get('search')
        if search:
            qs = qs.filter(
                models.Q(name__icontains=search) |
                models.Q(slug__icontains=search) |
                models.Q(contact_email__icontains=search)
            )

        serializer = TenantAdminSerializer(qs, many=True)
        return Response({
            'success': True,
            'count': qs.count(),
            'data': serializer.data
        })

    def post(self, request):
        serializer = TenantProvisionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        with transaction.atomic():
            tenant = Tenant.objects.create(
                name=data['name'],
                slug=data['slug'],
                institution_type=data['institution_type'],
                contact_email=data['contact_email'],
                contact_phone=data.get('contact_phone', ''),
                description=data.get('description', ''),
                default_currency=data.get('default_currency', 'USD'),
                timezone=data.get('timezone', 'UTC'),
                status=TenantStatus.ACTIVE
            )

            # Create Primary Domain
            TenantDomain.objects.create(
                tenant=tenant,
                hostname=data['primary_domain'],
                is_primary=True,
                is_verified=True,
                verified_at=timezone.now()
            )

            # Create Default Branding
            TenantBranding.objects.create(
                tenant=tenant,
                site_name=tenant.name,
                primary_colour='#111111',
                accent_colour=data.get('accent_colour', '#111111'),
                support_email=tenant.contact_email
            )

            # Create Default Settings
            TenantSettings.objects.create(
                tenant=tenant,
                public_registration_enabled=True,
                applications_enabled=True,
                learner_registration_enabled=True,
                certificates_enabled=True,
                payment_enabled=False,
                public_course_catalogue_enabled=True
            )

        full_tenant = Tenant.objects.prefetch_related('domains', 'branding', 'settings').get(id=tenant.id)
        return Response({
            'success': True,
            'message': f"Institution '{tenant.name}' provisioned successfully.",
            'data': TenantAdminSerializer(full_tenant).data
        }, status=status.HTTP_201_CREATED)


class TenantFleetDetailView(views.APIView):
    """
    Retrieve or update institutional status and configurations.
    """
    permission_classes = [IsPlatformOwner]

    def get(self, request, pk):
        tenant = get_object_or_404(
            Tenant.objects.prefetch_related('domains', 'branding', 'settings'),
            pk=pk
        )
        return Response({
            'success': True,
            'data': TenantAdminSerializer(tenant).data
        })

    def patch(self, request, pk):
        tenant = get_object_or_404(Tenant, pk=pk)
        allowed_fields = [
            'name', 'institution_type', 'description', 'status',
            'timezone', 'default_currency', 'contact_email', 'contact_phone'
        ]

        for field in allowed_fields:
            if field in request.data:
                setattr(tenant, field, request.data[field])

        tenant.save()
        tenant.refresh_from_db()
        return Response({
            'success': True,
            'message': f"Institution '{tenant.name}' updated successfully.",
            'data': TenantAdminSerializer(tenant).data
        })


class TenantFleetDomainsView(views.APIView):
    """
    Manage custom domains for an institution.
    """
    permission_classes = [IsPlatformOwner]

    def get(self, request, pk):
        tenant = get_object_or_404(Tenant, pk=pk)
        domains = tenant.domains.all().order_by('-is_primary', 'hostname')
        return Response({
            'success': True,
            'data': TenantDomainSerializer(domains, many=True).data
        })

    def post(self, request, pk):
        tenant = get_object_or_404(Tenant, pk=pk)
        serializer = CreateTenantDomainSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        is_primary = serializer.validated_data.get('is_primary', False)
        if is_primary:
            tenant.domains.all().update(is_primary=False)

        domain = TenantDomain.objects.create(
            tenant=tenant,
            hostname=serializer.validated_data['hostname'],
            is_primary=is_primary,
            is_verified=False
        )

        return Response({
            'success': True,
            'message': f"Domain '{domain.hostname}' attached to {tenant.name}.",
            'data': TenantDomainSerializer(domain).data
        }, status=status.HTTP_201_CREATED)


class TenantDomainVerifyView(views.APIView):
    """
    Mark a custom domain verified.
    """
    permission_classes = [IsPlatformOwner]

    def post(self, request, pk):
        domain = get_object_or_404(TenantDomain, pk=pk)
        domain.is_verified = True
        domain.verified_at = timezone.now()
        domain.save(update_fields=['is_verified', 'verified_at'])

        return Response({
            'success': True,
            'message': f"Domain '{domain.hostname}' has been verified.",
            'data': TenantDomainSerializer(domain).data
        })


class TenantFleetBrandingView(views.APIView):
    """
    Update white-label branding tokens for an institution.
    """
    permission_classes = [IsPlatformOwner]

    def patch(self, request, pk):
        tenant = get_object_or_404(Tenant, pk=pk)
        branding, _ = TenantBranding.objects.get_or_create(tenant=tenant)
        serializer = TenantBrandingSerializer(branding, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response({
            'success': True,
            'message': f"Branding tokens updated for {tenant.name}.",
            'data': serializer.data
        })


class TenantFleetSettingsView(views.APIView):
    """
    Update feature flags for an institution.
    """
    permission_classes = [IsPlatformOwner]

    def patch(self, request, pk):
        tenant = get_object_or_404(Tenant, pk=pk)
        tenant_settings, _ = TenantSettings.objects.get_or_create(tenant=tenant)
        serializer = TenantSettingsSerializer(tenant_settings, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response({
            'success': True,
            'message': f"Feature flags updated for {tenant.name}.",
            'data': serializer.data
        })


class PlatformFleetStatsView(views.APIView):
    """
    Global fleet KPIs and operational telemetry.
    """
    permission_classes = [IsPlatformOwner]

    def get(self, request):
        from apps.memberships.models import TenantMembership
        from django.contrib.auth import get_user_model

        User = get_user_model()

        total_tenants = Tenant.objects.count()
        active_tenants = Tenant.objects.filter(status=TenantStatus.ACTIVE).count()
        pending_tenants = Tenant.objects.filter(status=TenantStatus.PENDING).count()
        suspended_tenants = Tenant.objects.filter(status=TenantStatus.SUSPENDED).count()

        total_users = User.objects.count()
        total_memberships = TenantMembership.objects.filter(status='active').count()

        return Response({
            'success': True,
            'data': {
                'tenants': {
                    'total': total_tenants,
                    'active': active_tenants,
                    'pending': pending_tenants,
                    'suspended': suspended_tenants,
                },
                'users': {
                    'total_users': total_users,
                    'active_memberships': total_memberships,
                },
                'system': {
                    'status': 'operational',
                    'version': '1.0.0',
                    'database': 'PostgreSQL 17 (Connected)',
                    'cache': 'Redis / Celery (Ready)',
                }
            }
        })
