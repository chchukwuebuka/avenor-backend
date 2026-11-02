from decimal import Decimal
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework import status

from apps.accounts.models import User
from apps.tenants.models import Tenant
from apps.courses.models import Programme, Course, CourseOffering, AcademicStatus
from apps.enrollments.models import Enrollment, EnrollmentStatus
from apps.memberships.models import TenantMembership, Role, MembershipRole, MembershipStatus
from apps.analytics.models import (
    AuditLog,
    AuditAction,
    ScholarEngagementMetric,
    ComplianceReport,
    ComplianceReportType,
    ComplianceReportStatus,
)


class AnalyticsAndComplianceTests(TestCase):
    def setUp(self):
        self.client = APIClient()

        # Tenant
        self.tenant = Tenant.objects.create(
            name="Apex Executive Academy",
            slug="apex-analytics-test",
            contact_email="compliance@apex.test"
        )

        # Users
        self.dean = User.objects.create_user(
            email="dean@apex.test",
            password="Password123!",
            first_name="Prof",
            last_name="Hawthorne",
            is_staff=True
        )
        self.student = User.objects.create_user(
            email="scholar@apex.test",
            password="Password123!",
            first_name="Elena",
            last_name="Rostova"
        )
        self.other_student = User.objects.create_user(
            email="scholar2@apex.test",
            password="Password123!",
            first_name="Marcus",
            last_name="Vance"
        )

        # Role & Membership for Dean
        self.admin_role, _ = Role.objects.get_or_create(
            slug='institutional_admin',
            defaults={'name': 'Institutional Administrator'}
        )
        self.membership = TenantMembership.objects.create(
            tenant=self.tenant,
            user=self.dean,
            status=MembershipStatus.ACTIVE
        )
        MembershipRole.objects.create(membership=self.membership, role=self.admin_role)

        # Course, Offering & Enrollment
        self.prog = Programme.objects.create(
            tenant=self.tenant,
            name="Executive Leadership",
            slug="exec-leadership"
        )
        self.course = Course.objects.create(
            tenant=self.tenant,
            programme=self.prog,
            title="Strategic Negotiation",
            slug="strategic-negotiation",
            status=AcademicStatus.PUBLISHED
        )
        today = timezone.now().date()
        self.offering = CourseOffering.objects.create(
            tenant=self.tenant,
            course=self.course,
            offering_code="EXEC-2026-F",
            cohort_name="Fall 2026 Cohort",
            start_date=today,
            end_date=today + timezone.timedelta(days=90),
        )
        self.enrollment = Enrollment.objects.create(
            tenant=self.tenant,
            offering=self.offering,
            student=self.student,
            status=EnrollmentStatus.ACTIVE,
            grade="92.50",
            progress_percentage=85
        )

        # Sample Audit Log
        self.audit_log = AuditLog.objects.create(
            tenant=self.tenant,
            actor=self.dean,
            actor_email=self.dean.email,
            action=AuditAction.COURSE_PUBLISH,
            resource_type='Course',
            resource_id=str(self.course.id),
            changes={'status': 'published'}
        )

        # Engagement Metrics
        self.metric_elena = ScholarEngagementMetric.objects.create(
            tenant=self.tenant,
            scholar=self.student,
            course=self.course,
            total_time_spent_seconds=7200,  # 2 hours
            lessons_completed_count=6,
            quizzes_attempted_count=2,
            quizzes_passed_count=2,
            average_quiz_score=Decimal('90.00'),
            last_activity_at=timezone.now()
        )
        self.metric_marcus = ScholarEngagementMetric.objects.create(
            tenant=self.tenant,
            scholar=self.other_student,
            course=self.course,
            total_time_spent_seconds=3600,  # 1 hour
            lessons_completed_count=3,
            quizzes_attempted_count=1,
            quizzes_passed_count=1,
            average_quiz_score=Decimal('85.00'),
            last_activity_at=timezone.now()
        )

    def test_audit_log_access_and_permissions(self):
        # Scholar is forbidden from accessing institutional audit logs
        self.client.force_authenticate(user=self.student)
        resp_denied = self.client.get(
            "/api/v1/analytics/audit-logs/",
            HTTP_HOST=f"{self.tenant.slug}.avenor.test"
        )
        self.assertEqual(resp_denied.status_code, status.HTTP_403_FORBIDDEN)

        # Dean can access and filter audit logs
        self.client.force_authenticate(user=self.dean)
        resp = self.client.get(
            "/api/v1/analytics/audit-logs/",
            HTTP_HOST=f"{self.tenant.slug}.avenor.test"
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        results = resp.data.get('results', resp.data) if isinstance(resp.data, dict) else resp.data
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['action'], AuditAction.COURSE_PUBLISH)

    def test_scholar_engagement_isolation(self):
        # Scholar can only see their own engagement record
        self.client.force_authenticate(user=self.student)
        resp_scholar = self.client.get(
            "/api/v1/analytics/engagement/",
            HTTP_HOST=f"{self.tenant.slug}.avenor.test"
        )
        self.assertEqual(resp_scholar.status_code, status.HTTP_200_OK)
        results = resp_scholar.data.get('results', resp_scholar.data) if isinstance(resp_scholar.data, dict) else resp_scholar.data
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['scholar_email'], self.student.email)

        # Faculty can view all scholars' engagement metrics
        self.client.force_authenticate(user=self.dean)
        resp_faculty = self.client.get(
            "/api/v1/analytics/engagement/",
            HTTP_HOST=f"{self.tenant.slug}.avenor.test"
        )
        self.assertEqual(resp_faculty.status_code, status.HTTP_200_OK)
        results_all = resp_faculty.data.get('results', resp_faculty.data) if isinstance(resp_faculty.data, dict) else resp_faculty.data
        self.assertEqual(len(results_all), 2)

    def test_compliance_report_generation(self):
        self.client.force_authenticate(user=self.dean)
        gen_url = "/api/v1/analytics/compliance/reports/generate/"

        resp = self.client.post(
            gen_url,
            {
                'report_type': ComplianceReportType.FERPA_AUDIT,
                'title': 'Apex Executive Academy — FERPA Compliance Package',
            },
            format='json',
            HTTP_HOST=f"{self.tenant.slug}.avenor.test"
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resp.data['status'], ComplianceReportStatus.COMPLETED)
        self.assertEqual(resp.data['report_type'], ComplianceReportType.FERPA_AUDIT)
        self.assertIn('active_scholars_count', resp.data['summary'])

        # Check that audit log was generated for the compliance report export
        audit = AuditLog.objects.filter(
            tenant=self.tenant,
            action=AuditAction.DATA_EXPORT
        ).first()
        self.assertIsNotNone(audit)
        self.assertEqual(audit.actor, self.dean)

    def test_dashboard_analytics_kpi_summary(self):
        self.client.force_authenticate(user=self.dean)
        dash_url = "/api/v1/analytics/dashboard/"

        resp = self.client.get(dash_url, HTTP_HOST=f"{self.tenant.slug}.avenor.test")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        data = resp.data

        self.assertEqual(data['total_active_scholars'], 1)
        self.assertEqual(data['total_courses'], 1)
        self.assertEqual(Decimal(data['average_assessment_score']), Decimal('87.50'))
        # 7200s + 3600s = 10800s / 3600 = 3.00 hours
        self.assertEqual(Decimal(data['total_learning_hours']), Decimal('3.00'))
        self.assertTrue(len(data['recent_activity']) >= 1)
