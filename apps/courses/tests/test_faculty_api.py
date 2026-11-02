from datetime import date
from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase
from apps.tenants.models import Tenant, TenantDomain
from apps.memberships.models import (
    Permission,
    Role,
    RolePermission,
    TenantMembership,
    MembershipRole,
    MembershipStatus,
)
from apps.courses.models import Course, Module, AcademicStatus

User = get_user_model()


class FacultyCourseAPITests(APITestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name="Delta Academy", slug="delta", contact_email="admin@delta.edu")
        self.domain = TenantDomain.objects.create(tenant=self.tenant, hostname="delta.avenor.local", is_primary=True, is_verified=True)

        # Users
        self.instructor = User.objects.create_user(email="faculty@delta.edu", password="Password123!")
        self.unprivileged_user = User.objects.create_user(email="student@delta.edu", password="Password123!")

        # Permissions and Roles
        self.perm_create = Permission.objects.create(codename="courses.create", name="Create Courses", module="courses")
        self.perm_edit = Permission.objects.create(codename="courses.edit", name="Edit Courses", module="courses")
        self.perm_publish = Permission.objects.create(codename="courses.publish", name="Publish Courses", module="courses")

        self.role_instructor = Role.objects.create(slug="instructor", name="Instructor")
        RolePermission.objects.create(role=self.role_instructor, permission=self.perm_create)
        RolePermission.objects.create(role=self.role_instructor, permission=self.perm_edit)
        RolePermission.objects.create(role=self.role_instructor, permission=self.perm_publish)

        self.role_learner = Role.objects.create(slug="learner", name="Learner")

        # Memberships
        self.membership_inst = TenantMembership.objects.create(
            tenant=self.tenant,
            user=self.instructor,
            status=MembershipStatus.ACTIVE
        )
        MembershipRole.objects.create(membership=self.membership_inst, role=self.role_instructor)

        self.membership_learner = TenantMembership.objects.create(
            tenant=self.tenant,
            user=self.unprivileged_user,
            status=MembershipStatus.ACTIVE
        )
        MembershipRole.objects.create(membership=self.membership_learner, role=self.role_learner)

    def test_unauthorized_user_cannot_author_course(self):
        self.client.force_authenticate(user=self.unprivileged_user)
        res = self.client.post(
            '/api/v1/courses/manage/',
            {
                'title': 'Unauthorized Course',
                'slug': 'unauthorized-course',
                'short_description': 'Test description'
            },
            HTTP_HOST='delta.avenor.local',
            format='json'
        )
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

    def test_faculty_course_authoring_lifecycle(self):
        self.client.force_authenticate(user=self.instructor)

        # 1. Create Course
        create_res = self.client.post(
            '/api/v1/courses/manage/',
            {
                'title': 'Advanced Corporate Strategy',
                'slug': 'advanced-corporate-strategy',
                'short_description': 'Executive strategy course',
                'duration': '10 Weeks',
                'level': 'advanced'
            },
            HTTP_HOST='delta.avenor.local',
            format='json'
        )
        self.assertEqual(create_res.status_code, status.HTTP_201_CREATED)
        course_id = create_res.data['id']
        self.assertEqual(create_res.data['status'], 'draft')

        # 2. Add Syllabus Module
        mod_res = self.client.post(
            f'/api/v1/courses/manage/{course_id}/modules/',
            {'title': 'Module 1: Corporate Restructuring', 'order': 1},
            HTTP_HOST='delta.avenor.local',
            format='json'
        )
        self.assertEqual(mod_res.status_code, status.HTTP_201_CREATED)
        module_id = mod_res.data['id']

        # 3. Add Lesson
        lesson_res = self.client.post(
            f'/api/v1/courses/manage/modules/{module_id}/lessons/',
            {
                'title': 'Lesson 1.1: Fiduciary Responsibilities',
                'lesson_type': 'article',
                'duration_minutes': 30
            },
            HTTP_HOST='delta.avenor.local',
            format='json'
        )
        self.assertEqual(lesson_res.status_code, status.HTTP_201_CREATED)

        # 4. Add Cohort Offering
        cohort_res = self.client.post(
            f'/api/v1/courses/manage/{course_id}/cohorts/',
            {
                'offering_code': 'DELTA-CORP-2026',
                'cohort_name': 'Inaugural Executive Intake',
                'start_date': '2026-05-01',
                'end_date': '2026-07-15',
                'price': '1500.00',
                'currency': 'USD',
                'delivery_mode': 'hybrid'
            },
            HTTP_HOST='delta.avenor.local',
            format='json'
        )
        self.assertEqual(cohort_res.status_code, status.HTTP_201_CREATED)

        # 5. Publish Course
        publish_res = self.client.post(
            f'/api/v1/courses/manage/{course_id}/publish/',
            HTTP_HOST='delta.avenor.local'
        )
        self.assertEqual(publish_res.status_code, status.HTTP_200_OK)
        self.assertEqual(publish_res.data['status'], 'published')
