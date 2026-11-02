from rest_framework import serializers
from .models import Tenant, TenantDomain, TenantBranding, TenantSettings

class TenantDomainSerializer(serializers.ModelSerializer):
    class Meta:
        model = TenantDomain
        fields = [
            'id',
            'hostname',
            'is_primary',
            'is_verified',
            'verified_at',
            'created_at',
        ]
        read_only_fields = ['id', 'is_verified', 'verified_at', 'created_at']

class TenantBrandingSerializer(serializers.ModelSerializer):
    class Meta:
        model = TenantBranding
        fields = [
            'site_name',
            'logo',
            'favicon',
            'primary_colour',
            'secondary_colour',
            'accent_colour',
            'background_colour',
            'text_colour',
            'heading_font',
            'body_font',
            'support_email',
            'support_phone',
            'footer_text',
        ]

class TenantSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = TenantSettings
        fields = [
            'public_registration_enabled',
            'applications_enabled',
            'learner_registration_enabled',
            'certificates_enabled',
            'payment_enabled',
            'public_course_catalogue_enabled',
            'maintenance_message',
        ]

class TenantPublicSerializer(serializers.ModelSerializer):
    domains = TenantDomainSerializer(many=True, read_only=True)
    branding = TenantBrandingSerializer(read_only=True)
    settings = TenantSettingsSerializer(read_only=True)

    class Meta:
        model = Tenant
        fields = [
            'id',
            'name',
            'slug',
            'institution_type',
            'description',
            'status',
            'timezone',
            'default_currency',
            'contact_email',
            'contact_phone',
            'domains',
            'branding',
            'settings',
            'created_at',
        ]
        read_only_fields = fields
