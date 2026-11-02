from rest_framework import serializers
from .models import Tenant, TenantDomain, TenantBranding, TenantSettings, InstitutionType, TenantStatus


class TenantDomainSerializer(serializers.ModelSerializer):
    class Meta:
        model = TenantDomain
        fields = [
            'id',
            'hostname',
            'is_primary',
            'is_verified',
            'verification_token',
            'verified_at',
            'created_at',
        ]
        read_only_fields = ['id', 'is_verified', 'verification_token', 'verified_at', 'created_at']


class CreateTenantDomainSerializer(serializers.ModelSerializer):
    class Meta:
        model = TenantDomain
        fields = ['hostname', 'is_primary']

    def validate_hostname(self, value):
        cleaned = value.lower().strip()
        if TenantDomain.objects.filter(hostname=cleaned).exists():
            raise serializers.ValidationError("This hostname is already assigned to an institution.")
        return cleaned


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


class TenantAdminSerializer(serializers.ModelSerializer):
    domains = TenantDomainSerializer(many=True, read_only=True)
    branding = TenantBrandingSerializer(read_only=True)
    settings = TenantSettingsSerializer(read_only=True)
    members_count = serializers.SerializerMethodField()
    primary_domain = serializers.SerializerMethodField()

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
            'members_count',
            'primary_domain',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'members_count', 'primary_domain', 'created_at', 'updated_at']

    def get_members_count(self, obj):
        try:
            return obj.memberships.filter(status='active').count()
        except Exception:
            return 0

    def get_primary_domain(self, obj):
        dom = obj.domains.filter(is_primary=True).first()
        return dom.hostname if dom else None


class TenantProvisionSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=255)
    slug = serializers.SlugField(max_length=100)
    institution_type = serializers.ChoiceField(
        choices=InstitutionType.choices,
        default=InstitutionType.PROFESSIONAL_TRAINING
    )
    contact_email = serializers.EmailField()
    contact_phone = serializers.CharField(max_length=32, required=False, allow_blank=True, default='')
    primary_domain = serializers.CharField(max_length=255)
    description = serializers.CharField(required=False, allow_blank=True, default='')
    default_currency = serializers.CharField(max_length=10, default='USD')
    timezone = serializers.CharField(max_length=50, default='UTC')
    accent_colour = serializers.CharField(max_length=16, default='#111111')

    def validate_slug(self, value):
        cleaned = value.lower().strip()
        if Tenant.objects.filter(slug=cleaned).exists():
            raise serializers.ValidationError("An institution with this slug already exists.")
        return cleaned

    def validate_primary_domain(self, value):
        cleaned = value.lower().strip()
        if TenantDomain.objects.filter(hostname=cleaned).exists():
            raise serializers.ValidationError("This hostname is already in use by another institution.")
        return cleaned
