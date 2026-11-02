from rest_framework import serializers
from .models import (
    AuditLog,
    ScholarEngagementMetric,
    ComplianceReport,
    ComplianceReportType,
    ComplianceReportStatus,
)


class AuditLogSerializer(serializers.ModelSerializer):
    action_display = serializers.CharField(source='get_action_display', read_only=True)

    class Meta:
        model = AuditLog
        fields = [
            'id',
            'tenant',
            'actor',
            'actor_email',
            'action',
            'action_display',
            'resource_type',
            'resource_id',
            'ip_address',
            'user_agent',
            'changes',
            'created_at',
        ]
        read_only_fields = fields


class ScholarEngagementMetricSerializer(serializers.ModelSerializer):
    scholar_name = serializers.SerializerMethodField()
    scholar_email = serializers.CharField(source='scholar.email', read_only=True)
    course_title = serializers.CharField(source='course.title', read_only=True)

    class Meta:
        model = ScholarEngagementMetric
        fields = [
            'id',
            'tenant',
            'scholar',
            'scholar_name',
            'scholar_email',
            'course',
            'course_title',
            'total_time_spent_seconds',
            'lessons_completed_count',
            'quizzes_attempted_count',
            'quizzes_passed_count',
            'average_quiz_score',
            'assignments_submitted_count',
            'last_activity_at',
        ]
        read_only_fields = fields

    def get_scholar_name(self, obj):
        name = f"{obj.scholar.first_name} {obj.scholar.last_name}".strip()
        return name if name else obj.scholar.email


class ComplianceReportSerializer(serializers.ModelSerializer):
    report_type_display = serializers.CharField(source='get_report_type_display', read_only=True)
    requested_by_name = serializers.SerializerMethodField()

    class Meta:
        model = ComplianceReport
        fields = [
            'id',
            'tenant',
            'report_type',
            'report_type_display',
            'title',
            'status',
            'requested_by',
            'requested_by_name',
            'file_url',
            'summary',
            'completed_at',
            'created_at',
        ]
        read_only_fields = ['id', 'tenant', 'report_type_display', 'status', 'file_url', 'summary', 'completed_at', 'created_at']

    def get_requested_by_name(self, obj):
        if not obj.requested_by:
            return 'System Automated'
        name = f"{obj.requested_by.first_name} {obj.requested_by.last_name}".strip()
        return name if name else obj.requested_by.email


class GenerateComplianceReportSerializer(serializers.Serializer):
    report_type = serializers.ChoiceField(choices=ComplianceReportType.choices)
    title = serializers.CharField(max_length=255, required=False)


class AnalyticsDashboardSummarySerializer(serializers.Serializer):
    total_active_scholars = serializers.IntegerField()
    total_courses = serializers.IntegerField()
    completion_rate_percentage = serializers.DecimalField(max_digits=5, decimal_places=2)
    average_assessment_score = serializers.DecimalField(max_digits=5, decimal_places=2)
    total_learning_hours = serializers.DecimalField(max_digits=8, decimal_places=2)
    certificates_issued_count = serializers.IntegerField()
    recent_activity = serializers.ListField(child=serializers.DictField())
