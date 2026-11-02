from rest_framework import serializers
from django.contrib.auth import get_user_model
from apps.tenants.models import Tenant
from .models import Permission, Role, TenantMembership, MembershipRole, StaffInvitation, MembershipStatus

User = get_user_model()


class PermissionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Permission
        fields = ['id', 'codename', 'name', 'module', 'description']


class RoleSerializer(serializers.ModelSerializer):
    permissions = serializers.SlugRelatedField(
        many=True,
        read_only=True,
        slug_field='codename'
    )

    class Meta:
        model = Role
        fields = ['id', 'slug', 'name', 'description', 'is_platform_role', 'permissions']


class TenantMemberUserSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(source='get_full_name', read_only=True)

    class Meta:
        model = User
        fields = ['id', 'email', 'first_name', 'last_name', 'full_name', 'profile_image']


class TenantSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = Tenant
        fields = ['id', 'name', 'slug']


class TenantMembershipSerializer(serializers.ModelSerializer):
    user = TenantMemberUserSerializer(read_only=True)
    tenant = TenantSummarySerializer(read_only=True)
    roles = RoleSerializer(many=True, read_only=True)
    role_slugs = serializers.SerializerMethodField()

    class Meta:
        model = TenantMembership
        fields = [
            'id',
            'tenant',
            'user',
            'roles',
            'role_slugs',
            'status',
            'joined_at',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'tenant', 'user', 'joined_at', 'created_at', 'updated_at']

    def get_role_slugs(self, obj):
        return list(obj.roles.values_list('slug', flat=True))


class UpdateMembershipSerializer(serializers.Serializer):
    role_slugs = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        allow_empty=False
    )
    status = serializers.ChoiceField(
        choices=MembershipStatus.choices,
        required=False
    )

    def validate_role_slugs(self, slugs):
        roles = Role.objects.filter(slug__in=slugs, is_platform_role=False)
        found_slugs = set(roles.values_list('slug', flat=True))
        missing = set(slugs) - found_slugs
        if missing:
            raise serializers.ValidationError(f"Invalid institutional roles: {', '.join(missing)}")
        return list(found_slugs)


class StaffInvitationSerializer(serializers.ModelSerializer):
    role = RoleSerializer(read_only=True)
    invited_by_email = serializers.EmailField(source='invited_by.email', read_only=True)
    is_valid = serializers.BooleanField(read_only=True)

    class Meta:
        model = StaffInvitation
        fields = [
            'id',
            'email',
            'role',
            'token',
            'status',
            'invited_by_email',
            'expires_at',
            'accepted_at',
            'created_at',
            'is_valid',
        ]
        read_only_fields = fields


class CreateStaffInvitationSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)
    role_slug = serializers.CharField(required=True)

    def validate_role_slug(self, value):
        role = Role.objects.filter(slug=value, is_platform_role=False).first()
        if not role:
            raise serializers.ValidationError(f"Role '{value}' is not a valid institutional role.")
        return value

    def validate(self, attrs):
        tenant = self.context['tenant']
        email = attrs['email'].lower()

        # Check if already an active member
        if TenantMembership.objects.filter(
            tenant=tenant,
            user__email=email,
            status=MembershipStatus.ACTIVE
        ).exists():
            raise serializers.ValidationError({'email': 'This user is already an active member of this institution.'})

        # Check for pending invitation
        existing_invite = StaffInvitation.objects.filter(
            tenant=tenant,
            email=email,
            status='pending'
        ).first()

        if existing_invite and existing_invite.is_valid:
            raise serializers.ValidationError({'email': 'A pending invitation already exists for this email.'})

        return attrs


class AcceptInvitationSerializer(serializers.Serializer):
    token = serializers.CharField(required=True)
    first_name = serializers.CharField(required=False, allow_blank=True)
    last_name = serializers.CharField(required=False, allow_blank=True)
    password = serializers.CharField(required=False, allow_blank=True, write_only=True)
