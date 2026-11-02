from datetime import date, timedelta
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework import status
from apps.accounts.models import User
from apps.tenants.models import Tenant
from apps.courses.models import Programme, Course, Module, Lesson, CourseOffering, AcademicStatus
from apps.enrollments.models import Enrollment, LessonProgress, EnrollmentStatus


class EnrollmentModelAndAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()

        # Tenant
        self.tenant = Tenant.objects.create(
            name="Apex Institute",
            slug="apex-test",
            contact_email="admin@apex.test"
        )

        # Student User
        self.student = User.objects.create_user(
            email="student@apex.test",
            password="Password123!",
            first_name="Alex",
            last_name="Kim"
        )

        # Faculty / Staff User
        self.faculty = User.objects.create_user(
            email="prof@apex.test",
            password="Password123!",
            first_name="Prof",
            last_name="Davis",
            is_staff=True
        )

        # Course & Offering
        self.prog = Programme.objects.create(
            tenant=self.tenant,
            name="Applied Science",
            slug="applied-science"
        )
        self.course = Course.objects.create(
            tenant=self.tenant,
            programme=self.prog,
            title="Cloud Architecture",
            slug="cloud-architecture",
            short_description="Cloud scale engineering",
            status=AcademicStatus.PUBLISHED
        )
        self.module = Module.objects.create(
            tenant=self.tenant,
            course=self.course,
            title="Module 1: Infrastructure",
            order=1
        )
        self.lesson1 = Lesson.objects.create(
            tenant=self.tenant,
            module=self.module,
            title="Lesson 1: Virtual Networks",
            order=1
        )
        self.lesson2 = Lesson.objects.create(
            tenant=self.tenant,
            module=self.module,
            title="Lesson 2: Kubernetes Cluster Design",
            order=2
        )

        self.offering = CourseOffering.objects.create(
            tenant=self.tenant,
            course=self.course,
            offering_code="CA-2026-01",
            cohort_name="Spring Intake",
            start_date=date.today(),
            end_date=date.today() + timedelta(days=60),
            status="open"
        )

    def test_enrollment_lifecycle_and_progress_recalculation(self):
        # 1. Create Enrollment
        enrollment = Enrollment.objects.create(
            tenant=self.tenant,
            student=self.student,
            offering=self.offering,
            status=EnrollmentStatus.ACTIVE
        )
        self.assertEqual(enrollment.progress_percentage, 0)
        self.assertIsNone(enrollment.completed_at)

        # 2. Complete Lesson 1
        prog1 = LessonProgress.objects.create(
            tenant=self.tenant,
            enrollment=enrollment,
            lesson=self.lesson1,
            is_completed=True,
            completed_at=timezone.now()
        )
        enrollment.recalculate_progress()
        self.assertEqual(enrollment.progress_percentage, 50)
        self.assertEqual(enrollment.status, EnrollmentStatus.ACTIVE)

        # 3. Complete Lesson 2 (100% progress)
        prog2 = LessonProgress.objects.create(
            tenant=self.tenant,
            enrollment=enrollment,
            lesson=self.lesson2,
            is_completed=True,
            completed_at=timezone.now()
        )
        enrollment.recalculate_progress()
        self.assertEqual(enrollment.progress_percentage, 100)
        self.assertEqual(enrollment.status, EnrollmentStatus.COMPLETED)
        self.assertIsNotNone(enrollment.completed_at)

    def test_enrollment_uniqueness(self):
        Enrollment.objects.create(
            tenant=self.tenant,
            student=self.student,
            offering=self.offering
        )
        with self.assertRaises(Exception):
            Enrollment.objects.create(
                tenant=self.tenant,
                student=self.student,
                offering=self.offering
            )

    def test_toggle_lesson_api_endpoint(self):
        enrollment = Enrollment.objects.create(
            tenant=self.tenant,
            student=self.student,
            offering=self.offering
        )

        self.client.force_authenticate(user=self.student)
        url = f"/api/v1/enrollments/{enrollment.id}/toggle-lesson/"

        # Toggle to completed
        response = self.client.post(url, {
            'lesson_id': str(self.lesson1.id),
            'is_completed': True,
            'time_spent_seconds': 600
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['is_completed'])
        self.assertEqual(response.data['time_spent_seconds'], 600)

        enrollment.refresh_from_db()
        self.assertEqual(enrollment.progress_percentage, 50)

    def test_scholar_stats_api(self):
        enrollment = Enrollment.objects.create(
            tenant=self.tenant,
            student=self.student,
            offering=self.offering,
            status=EnrollmentStatus.ACTIVE
        )
        LessonProgress.objects.create(
            tenant=self.tenant,
            enrollment=enrollment,
            lesson=self.lesson1,
            is_completed=True
        )

        self.client.force_authenticate(user=self.student)
        url = "/api/v1/enrollments/stats/"
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['total_enrolled_courses'], 1)
        self.assertEqual(response.data['lessons_completed'], 1)
        self.assertIn('cumulative_gpa', response.data)
