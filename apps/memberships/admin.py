from django.contrib import admin
from .models import Permission, Role, RolePermission, TenantMembership, MembershipRole, StaffInvitation


class RolePermissionInline(admin.TabularInline):
    model = RolePermission
    extra = 1


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'is_platform_role', 'created_at')
    list_filter = ('is_platform_role',)
    search_fields = ('name', 'slug', 'description')
    inlines = [RolePermissionInline]


@admin.register(Permission)
class PermissionAdmin(admin.ModelAdmin):
    list_display = ('codename', 'name', 'module', 'created_at')
    list_filter = ('module',)
    search_fields = ('codename', 'name')


class MembershipRoleInline(admin.TabularInline):
    model = MembershipRole
    extra = 1


@admin.register(TenantMembership)
class TenantMembershipAdmin(admin.ModelAdmin):
    list_display = ('user', 'tenant', 'status', 'joined_at')
    list_filter = ('status', 'tenant')
    search_fields = ('user__email', 'tenant__name', 'tenant__slug')
    inlines = [MembershipRoleInline]


@admin.register(StaffInvitation)
class StaffInvitationAdmin(admin.ModelAdmin):
    list_display = ('email', 'tenant', 'role', 'status', 'expires_at', 'created_at')
    list_filter = ('status', 'tenant')
    search_fields = ('email', 'token', 'tenant__name')
