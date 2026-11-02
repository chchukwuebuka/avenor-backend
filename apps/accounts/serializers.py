from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password

User = get_user_model()

class UserSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(source='get_full_name', read_only=True)
    memberships = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            'id',
            'email',
            'first_name',
            'last_name',
            'other_names',
            'phone_number',
            'full_name',
            'profile_image',
            'is_active',
            'is_platform_staff',
            'email_verified',
            'memberships',
            'date_joined',
            'last_login',
        ]
        read_only_fields = ['id', 'email', 'is_active', 'is_platform_staff', 'email_verified', 'memberships', 'date_joined', 'last_login']

    def get_memberships(self, obj):
        try:
            from apps.memberships.models import TenantMembership, MembershipStatus
            memberships = TenantMembership.objects.filter(
                user=obj,
                status=MembershipStatus.ACTIVE
            ).select_related('tenant').prefetch_related('roles')
            return [
                {
                    'tenant_id': str(m.tenant.id),
                    'tenant_name': m.tenant.name,
                    'tenant_slug': m.tenant.slug,
                    'roles': list(m.roles.values_list('slug', flat=True)),
                    'is_admin': m.is_admin,
                }
                for m in memberships
            ]
        except Exception:
            return []

class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=True, validators=[validate_password])
    password_confirm = serializers.CharField(write_only=True, required=True)

    class Meta:
        model = User
        fields = [
            'id',
            'email',
            'first_name',
            'last_name',
            'phone_number',
            'password',
            'password_confirm',
        ]
        read_only_fields = ['id']

    def validate(self, attrs):
        if attrs['password'] != attrs['password_confirm']:
            raise serializers.ValidationError({'password_confirm': 'Passwords do not match.'})
        return attrs

    def create(self, validated_data):
        validated_data.pop('password_confirm')
        password = validated_data.pop('password')
        user = User.objects.create_user(password=password, **validated_data)
        return user

class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token['email'] = user.email
        token['full_name'] = user.get_full_name()
        token['is_platform_staff'] = user.is_platform_staff
        token['is_superuser'] = user.is_superuser
        return token

    def validate(self, attrs):
        data = super().validate(attrs)
        data['user'] = UserSerializer(self.user).data
        return data

class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(required=True)
    new_password = serializers.CharField(required=True, validators=[validate_password])

    def validate_old_password(self, value):
        user = self.context['request'].user
        if not user.check_password(value):
            raise serializers.ValidationError('Current password is not correct.')
        return value
