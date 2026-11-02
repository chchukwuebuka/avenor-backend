from decimal import Decimal
from django.core.management.base import BaseCommand
from django.utils import timezone
from apps.tenants.models import Tenant
from apps.accounts.models import User
from apps.courses.models import Course
from apps.analytics.models import (
    AuditLog,
    AuditAction,
    ScholarEngagementMetric,
    ComplianceReport,
    ComplianceReportType,
    ComplianceReportStatus,
)


class Command(BaseCommand):
    help = 'Seeds compliance audit logs, scholar engagement telemetry, and institutional reports.'

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("Seeding analytics and compliance records..."))

        now = timezone.now()

        # 1. Apex Executive Academy Telemetry
        apex = Tenant.objects.filter(slug='apex').first()
        if apex:
            elena = User.objects.filter(email='elena.rostova@apex.test').first()
            faculty = User.objects.filter(email='faculty.lead@apex.test').first() or User.objects.filter(is_staff=True).first()
            course = Course.objects.filter(tenant=apex).first()

            if elena and course:
                # Engagement Metric
                ScholarEngagementMetric.objects.update_or_create(
                    tenant=apex,
                    scholar=elena,
                    course=course,
                    defaults={
                        'total_time_spent_seconds': 14820,  # ~4.1 hours
                        'lessons_completed_count': 12,
                        'quizzes_attempted_count': 3,
                        'quizzes_passed_count': 3,
                        'average_quiz_score': Decimal('94.50'),
                        'assignments_submitted_count': 2,
                        'last_activity_at': now - timezone.timedelta(hours=2),
                    }
                )
                self.stdout.write(f"  Configured engagement metric for Elena in {course.title}.")

            # Audit Logs
            audit_events = [
                (AuditAction.USER_LOGIN, 'User', str(elena.id) if elena else '', elena.email if elena else 'elena@apex.test', '192.168.1.45', {}),
                (AuditAction.COURSE_PUBLISH, 'Course', str(course.id) if course else '', faculty.email if faculty else 'dean@apex.test', '10.0.0.12', {'status': 'published'}),
                (AuditAction.GRADE_SUBMIT, 'AssignmentSubmission', 'sub-99124', faculty.email if faculty else 'dean@apex.test', '10.0.0.12', {'score': 95, 'graded_by': 'Prof. Vance'}),
                (AuditAction.CERTIFICATE_ISSUE, 'Certificate', 'cert-apex-elena', 'system@avenor.test', '127.0.0.1', {'recipient': elena.email if elena else 'elena@apex.test'}),
            ]

            for action, res_type, res_id, actor_email, ip, changes in audit_events:
                AuditLog.objects.create(
                    tenant=apex,
                    actor=faculty if 'dean' in actor_email else elena,
                    actor_email=actor_email,
                    action=action,
                    resource_type=res_type,
                    resource_id=res_id,
                    ip_address=ip,
                    user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AvenorBrowser/1.0',
                    changes=changes,
                )
            self.stdout.write("  Created Apex compliance audit log trail.")

            # Compliance Report
            ComplianceReport.objects.update_or_create(
                tenant=apex,
                title="Apex Executive Academy — FERPA Scholar Privacy Audit (Q4)",
                defaults={
                    'report_type': ComplianceReportType.FERPA_AUDIT,
                    'status': ComplianceReportStatus.COMPLETED,
                    'requested_by': faculty,
                    'file_url': '/media/compliance/apex_ferpa_q4_2026.pdf',
                    'summary': {
                        'standard': 'FERPA 34 CFR Part 99',
                        'access_logs_reviewed': 148,
                        'unauthorized_disclosures': 0,
                        'compliance_status': 'fully_certified',
                        'data_protection_officer': 'Dr. Arthur Sterling',
                    },
                    'completed_at': now - timezone.timedelta(days=10),
                }
            )
            self.stdout.write("  Created Apex FERPA compliance report.")

        # 2. Northstar Technical Institute Telemetry
        northstar = Tenant.objects.filter(slug='northstar').first()
        if northstar:
            marcus = User.objects.filter(email='marcus.vance@northstar.test').first()
            ns_faculty = User.objects.filter(email='instructor@northstar.test').first() or User.objects.filter(is_staff=True).first()
            ns_course = Course.objects.filter(tenant=northstar).first()

            if marcus and ns_course:
                ScholarEngagementMetric.objects.update_or_create(
                    tenant=northstar,
                    scholar=marcus,
                    course=ns_course,
                    defaults={
                        'total_time_spent_seconds': 28400,  # ~7.9 hours
                        'lessons_completed_count': 18,
                        'quizzes_attempted_count': 5,
                        'quizzes_passed_count': 5,
                        'average_quiz_score': Decimal('98.00'),
                        'assignments_submitted_count': 4,
                        'last_activity_at': now - timezone.timedelta(hours=5),
                    }
                )
                self.stdout.write(f"  Configured engagement metric for Marcus in {ns_course.title}.")

            ComplianceReport.objects.update_or_create(
                tenant=northstar,
                title="Northstar Technical Institute — ABET Accreditation Telemetry",
                defaults={
                    'report_type': ComplianceReportType.ACCREDITATION_SUMMARY,
                    'status': ComplianceReportStatus.COMPLETED,
                    'requested_by': ns_faculty,
                    'file_url': '/media/compliance/northstar_abet_audit_2026.pdf',
                    'summary': {
                        'evaluating_body': 'ABET Computing Accreditation Commission',
                        'active_programmes': 2,
                        'learning_outcome_mastery_rate': '92.4%',
                        'curriculum_hours_verified': 120,
                    },
                    'completed_at': now - timezone.timedelta(days=5),
                }
            )
            self.stdout.write("  Created Northstar accreditation report.")

        self.stdout.write(self.style.SUCCESS("Successfully seeded analytics data!"))
