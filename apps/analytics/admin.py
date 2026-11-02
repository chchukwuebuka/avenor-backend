from django.contrib import admin
from .models import (
    AuditLog,
    ScholarEngagementMetric,
    ComplianceReport,
)


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ('actor_email', 'action', 'resource_type', 'resource_id', 'tenant', 'created_at')
    list_filter = ('action', 'resource_type', 'created_at')
    search_fields = ('actor_email', 'resource_id', 'tenant__slug', 'tenant__name')
    readonly_fields = [f.name for f in AuditLog._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(ScholarEngagementMetric)
class ScholarEngagementMetricAdmin(admin.ModelAdmin):
    list_display = ('scholar', 'course', 'tenant', 'total_time_spent_seconds', 'lessons_completed_count', 'average_quiz_score', 'last_activity_at')
    list_filter = ('course', 'tenant')
    search_fields = ('scholar__email', 'course__title', 'tenant__name')


@admin.register(ComplianceReport)
class ComplianceReportAdmin(admin.ModelAdmin):
    list_display = ('title', 'report_type', 'status', 'tenant', 'requested_by', 'completed_at', 'created_at')
    list_filter = ('report_type', 'status', 'created_at')
    search_fields = ('title', 'tenant__slug', 'requested_by__email')
