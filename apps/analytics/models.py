import uuid
from decimal import Decimal
from django.db import models
from django.utils import timezone
from apps.tenants.models import Tenant, TenantModel
from apps.accounts.models import User
from apps.courses.models import Course


class AuditAction(models.TextChoices):
    USER_LOGIN = 'user.login', 'User Authentication'
    USER_LOGOUT = 'user.logout', 'User Logout'
    COURSE_CREATE = 'course.create', 'Course Created'
    COURSE_PUBLISH = 'course.publish', 'Course Published'
    ENROLLMENT_CREATE = 'enrollment.create', 'Scholar Enrolled'
    ENROLLMENT_COMPLETE = 'enrollment.complete', 'Scholar Completed Course'
    GRADE_SUBMIT = 'grade.submit', 'Assessment Graded'
    CERTIFICATE_ISSUE = 'certificate.issue', 'Certificate Conferred'
    SETTINGS_UPDATE = 'settings.update', 'Tenant Settings Updated'
    ROLE_ASSIGN = 'role.assign', 'Security Role Assigned'
    DATA_EXPORT = 'data.export', 'Compliance Data Export'


class ComplianceReportType(models.TextChoices):
    FERPA_AUDIT = 'ferpa_audit', 'FERPA Scholar Access & Privacy Audit'
    ACADEMIC_PROGRESS = 'academic_progress', 'Cohort Progression & Completion'
    ACCREDITATION_SUMMARY = 'accreditation_summary', 'Institutional Accreditation Package'
    GDPR_DATA_EXPORT = 'gdpr_data_export', 'GDPR Article 15 Data Subject Export'


class ComplianceReportStatus(models.TextChoices):
    PENDING = 'pending', 'Pending'
    PROCESSING = 'processing', 'Processing'
    COMPLETED = 'completed', 'Completed'
    FAILED = 'failed', 'Failed'


class AuditLog(TenantModel):
    """
    Immutable compliance audit ledger capturing institutional actions, security events,
    and administrative configuration updates for FERPA, GDPR, and accreditation compliance.
    """
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='analytics_audit_logs')
    actor = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='audit_actions'
    )
    actor_email = models.CharField(max_length=255, db_index=True)
    action = models.CharField(max_length=64, choices=AuditAction.choices, db_index=True)
    resource_type = models.CharField(max_length=64, db_index=True)
    resource_id = models.CharField(max_length=128, blank=True, default='')

    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True, default='')
    changes = models.JSONField(default=dict, blank=True)

    class Meta:
        verbose_name = 'Audit Log'
        verbose_name_plural = 'Audit Logs'
        ordering = ['-created_at']

    def __str__(self):
        return f"[{self.tenant.slug}] {self.actor_email} -> {self.action} ({self.resource_type})"


class ScholarEngagementMetric(TenantModel):
    """
    Continuous scholar learning engagement, lecture retention, and assessment velocity metric.
    """
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='analytics_engagement_metrics')
    scholar = models.ForeignKey(User, on_delete=models.CASCADE, related_name='engagement_metrics')
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='engagement_metrics')

    total_time_spent_seconds = models.PositiveIntegerField(
        default=0,
        help_text="Aggregated active time in seconds across course lectures and materials."
    )
    lessons_completed_count = models.PositiveIntegerField(default=0)
    quizzes_attempted_count = models.PositiveIntegerField(default=0)
    quizzes_passed_count = models.PositiveIntegerField(default=0)
    average_quiz_score = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'))
    assignments_submitted_count = models.PositiveIntegerField(default=0)
    last_activity_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'Scholar Engagement Metric'
        verbose_name_plural = 'Scholar Engagement Metrics'
        unique_together = ('tenant', 'scholar', 'course')
        ordering = ['-last_activity_at']

    def __str__(self):
        return f"{self.scholar.email} in {self.course.title} — {self.total_time_spent_seconds}s active"


class ComplianceReport(TenantModel):
    """
    Generated institutional regulatory compliance documents (FERPA, GDPR, Accreditation).
    """
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='analytics_compliance_reports')
    report_type = models.CharField(max_length=64, choices=ComplianceReportType.choices)
    title = models.CharField(max_length=255)
    status = models.CharField(
        max_length=30,
        choices=ComplianceReportStatus.choices,
        default=ComplianceReportStatus.COMPLETED
    )
    requested_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='requested_compliance_reports'
    )
    file_url = models.CharField(max_length=512, blank=True, default='')
    summary = models.JSONField(default=dict, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'Compliance Report'
        verbose_name_plural = 'Compliance Reports'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.title} ({self.get_report_type_display()}) — [{self.status}]"
