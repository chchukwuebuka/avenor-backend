import uuid
from decimal import Decimal
from django.utils import timezone
from django.db.models import Avg, Sum, Count
from rest_framework import viewsets, status, permissions
from rest_framework.exceptions import PermissionDenied, NotFound, ValidationError
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from drf_spectacular.utils import extend_schema, OpenApiParameter

from apps.tenants.models import Tenant
from apps.courses.models import Course, AcademicStatus
from apps.enrollments.models import Enrollment, EnrollmentStatus
from apps.assessments.models import Certificate
from .models import (
    AuditLog,
    ScholarEngagementMetric,
    ComplianceReport,
    ComplianceReportType,
    ComplianceReportStatus,
    AuditAction,
)
from .serializers import (
    AuditLogSerializer,
    ScholarEngagementMetricSerializer,
    ComplianceReportSerializer,
    GenerateComplianceReportSerializer,
    AnalyticsDashboardSummarySerializer,
)


def get_request_tenant(request):
    tenant = getattr(request, 'tenant', None)
    if not tenant and request.user.is_authenticated:
        membership = request.user.tenant_memberships.first()
        if membership:
            tenant = membership.tenant
        else:
            tenant = Tenant.objects.first()
    return tenant


def is_faculty_or_admin(user, tenant=None):
    if not user.is_authenticated:
        return False
    if user.is_staff or user.is_superuser:
        return True
    qs = user.tenant_memberships.filter(
        roles__slug__in=['institutional_admin', 'dean', 'instructor', 'faculty', 'compliance_officer', 'billing_manager']
    )
    if tenant:
        qs = qs.filter(tenant=tenant)
    return qs.exists()


class AuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Compliance audit log ledger. Read-only records of actions, security events, and role grants.
    """
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = AuditLogSerializer

    def get_queryset(self):
        tenant = get_request_tenant(self.request)
        if not tenant:
            return AuditLog.objects.none()

        if not is_faculty_or_admin(self.request.user, tenant):
            raise PermissionDenied("Administrative or compliance officer privileges required to inspect audit logs.")

        qs = AuditLog.objects.filter(tenant=tenant)

        action_param = self.request.query_params.get('action')
        resource_type = self.request.query_params.get('resource_type')
        actor_email = self.request.query_params.get('actor_email')

        if action_param:
            qs = qs.filter(action=action_param)
        if resource_type:
            qs = qs.filter(resource_type=resource_type)
        if actor_email:
            qs = qs.filter(actor_email__icontains=actor_email)

        return qs.order_by('-created_at')


class ScholarEngagementViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Scholar learning velocity, time allocation, and assessment metrics.
    """
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = ScholarEngagementMetricSerializer

    def get_queryset(self):
        tenant = get_request_tenant(self.request)
        if not tenant:
            return ScholarEngagementMetric.objects.none()

        qs = ScholarEngagementMetric.objects.filter(tenant=tenant).select_related('scholar', 'course')

        # Scholars only inspect their own metrics; faculty can view all scholars
        if not is_faculty_or_admin(self.request.user, tenant):
            qs = qs.filter(scholar=self.request.user)

        course_id = self.request.query_params.get('course_id')
        scholar_id = self.request.query_params.get('scholar_id')

        if course_id:
            qs = qs.filter(course_id=course_id)
        if scholar_id and is_faculty_or_admin(self.request.user, tenant):
            qs = qs.filter(scholar_id=scholar_id)

        return qs.order_by('-last_activity_at')


class ComplianceReportViewSet(viewsets.ModelViewSet):
    """
    Regulatory compliance documentation package generator (FERPA, GDPR, Accreditation).
    """
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = ComplianceReportSerializer

    def get_queryset(self):
        tenant = get_request_tenant(self.request)
        if not tenant:
            return ComplianceReport.objects.none()

        if not is_faculty_or_admin(self.request.user, tenant):
            raise PermissionDenied("Administrative privileges required to inspect institutional compliance reports.")

        return ComplianceReport.objects.filter(tenant=tenant).order_by('-created_at')

    @extend_schema(summary="Generate institutional compliance package", request=GenerateComplianceReportSerializer)
    @action(detail=False, methods=['post'], url_path='generate')
    def generate(self, request):
        tenant = get_request_tenant(request)
        if not tenant:
            raise NotFound("No active institutional tenant context found.")

        if not is_faculty_or_admin(request.user, tenant):
            raise PermissionDenied("Administrative credentials required to initiate compliance audit generation.")

        serializer = GenerateComplianceReportSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        report_type = serializer.validated_data['report_type']
        title = serializer.validated_data.get('title')

        now = timezone.now()
        type_display = dict(ComplianceReportType.choices).get(report_type, report_type)
        if not title:
            title = f"{tenant.name} — {type_display} ({now.strftime('%B %Y')})"

        # Gather summary payload based on report type
        active_scholars = Enrollment.objects.filter(tenant=tenant, status=EnrollmentStatus.ACTIVE).values('student').distinct().count()
        completed_enrollments = Enrollment.objects.filter(tenant=tenant, status=EnrollmentStatus.COMPLETED).count()
        certificates_count = Certificate.objects.filter(tenant=tenant).count()

        summary_data = {
            'institution': tenant.name,
            'tenant_slug': tenant.slug,
            'generated_at': now.isoformat(),
            'active_scholars_count': active_scholars,
            'completed_credentials': completed_enrollments,
            'verified_certificates': certificates_count,
            'compliance_standard': report_type.upper(),
            'status': 'certified_compliant',
        }

        report = ComplianceReport.objects.create(
            tenant=tenant,
            report_type=report_type,
            title=title,
            status=ComplianceReportStatus.COMPLETED,
            requested_by=request.user,
            file_url=f"/media/compliance/{tenant.slug}_{report_type}_{now.strftime('%Y%m%d')}.pdf",
            summary=summary_data,
            completed_at=now
        )

        # Log audit action
        AuditLog.objects.create(
            tenant=tenant,
            actor=request.user,
            actor_email=request.user.email,
            action=AuditAction.DATA_EXPORT,
            resource_type='ComplianceReport',
            resource_id=str(report.id),
            changes={'report_type': report_type, 'title': title}
        )

        return Response(ComplianceReportSerializer(report).data, status=status.HTTP_201_CREATED)


class DashboardAnalyticsView(APIView):
    """
    Aggregated operational KPIs and telemetry dashboard for institutional leadership.
    """
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(summary="Get institutional executive KPI analytics summary", responses=AnalyticsDashboardSummarySerializer)
    def get(self, request):
        tenant = get_request_tenant(request)
        if not tenant:
            raise NotFound("No active institutional tenant context found.")

        if not is_faculty_or_admin(request.user, tenant):
            raise PermissionDenied("Faculty or administrative authorization required for analytics telemetry.")

        # 1. Total active scholars
        active_scholars = Enrollment.objects.filter(
            tenant=tenant,
            status=EnrollmentStatus.ACTIVE
        ).values('student').distinct().count()

        # 2. Total published courses
        total_courses = Course.objects.filter(
            tenant=tenant,
            status=AcademicStatus.PUBLISHED
        ).count()

        # 3. Completion rate
        total_enrollments = Enrollment.objects.filter(tenant=tenant).count()
        completed_enrollments = Enrollment.objects.filter(
            tenant=tenant,
            status=EnrollmentStatus.COMPLETED
        ).count()
        completion_rate = Decimal('0.00')
        if total_enrollments > 0:
            completion_rate = round(Decimal(completed_enrollments) / Decimal(total_enrollments) * 100, 2)

        # 4. Average assessment score
        avg_score_res = ScholarEngagementMetric.objects.filter(
            tenant=tenant
        ).aggregate(avg_score=Avg('average_quiz_score'))
        avg_score = round(Decimal(avg_score_res['avg_score'] or 0), 2)

        # 5. Total learning hours
        total_seconds_res = ScholarEngagementMetric.objects.filter(
            tenant=tenant
        ).aggregate(total_sec=Sum('total_time_spent_seconds'))
        total_seconds = total_seconds_res['total_sec'] or 0
        total_hours = round(Decimal(total_seconds) / Decimal(3600), 2)

        # 6. Certificates issued
        certs_count = Certificate.objects.filter(tenant=tenant).count()

        # 7. Recent activity (last 10 audit logs)
        recent_logs = AuditLog.objects.filter(tenant=tenant).order_by('-created_at')[:10]
        recent_activity = [
            {
                'id': str(log.id),
                'actor_email': log.actor_email,
                'action': log.action,
                'action_display': log.get_action_display(),
                'resource_type': log.resource_type,
                'created_at': log.created_at.isoformat(),
            }
            for log in recent_logs
        ]

        data = {
            'total_active_scholars': active_scholars,
            'total_courses': total_courses,
            'completion_rate_percentage': completion_rate,
            'average_assessment_score': avg_score,
            'total_learning_hours': total_hours,
            'certificates_issued_count': certs_count,
            'recent_activity': recent_activity,
        }

        serializer = AnalyticsDashboardSummarySerializer(data=data)
        serializer.is_valid(raise_exception=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
