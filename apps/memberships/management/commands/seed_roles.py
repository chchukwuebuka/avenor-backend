from django.core.management.base import BaseCommand
from django.db import transaction
from apps.memberships.models import Permission, Role, RolePermission


PERMISSIONS = [
    # Courses
    ('courses.view', 'View Courses & Curriculum', 'courses', 'Permission to browse courses and materials.'),
    ('courses.create', 'Create Courses & Modules', 'courses', 'Permission to create courses, modules, and lessons.'),
    ('courses.edit', 'Edit Course Content & Lessons', 'courses', 'Permission to edit course metadata and instructional content.'),
    ('courses.publish', 'Publish & Archive Courses', 'courses', 'Permission to change course publication status.'),
    ('courses.delete', 'Delete Courses', 'courses', 'Permission to permanently remove courses.'),

    # Memberships
    ('members.view', 'View Institutional Members', 'memberships', 'Permission to browse member directory and faculty roster.'),
    ('members.invite', 'Invite Staff & Faculty', 'memberships', 'Permission to send invitation links to staff and educators.'),
    ('members.edit_role', 'Assign & Edit Member Roles', 'memberships', 'Permission to assign roles to institutional members.'),
    ('members.suspend', 'Suspend & Reactivate Members', 'memberships', 'Permission to suspend or reinstate membership access.'),
    ('members.remove', 'Remove Institutional Members', 'memberships', 'Permission to remove members from the institution.'),

    # Admissions
    ('admissions.view', 'View Enrolment Applications', 'admissions', 'Permission to view incoming student applications.'),
    ('admissions.manage', 'Approve & Manage Applications', 'admissions', 'Permission to accept or reject enrolment requests.'),

    # Assessments
    ('assessments.view', 'View Student Submissions', 'assessments', 'Permission to view submitted student coursework and quizzes.'),
    ('assessments.grade', 'Grade Assignments & Issue Certifications', 'assessments', 'Permission to grade assignments and issue certificates.'),

    # Billing
    ('billing.view', 'View Institutional Invoices & Subscriptions', 'billing', 'Permission to view financial invoices and platform plan.'),
    ('billing.manage', 'Manage Payment Gateways & Subscription Plans', 'billing', 'Permission to configure payment processors and subscriptions.'),

    # Analytics
    ('analytics.view', 'Access Institutional Dashboards & Metrics', 'analytics', 'Permission to view learner engagement and completion metrics.'),

    # Settings
    ('settings.view', 'View Institutional Branding & Settings', 'settings', 'Permission to view branding, domains, and configurations.'),
    ('settings.edit', 'Modify Institutional Branding & Settings', 'settings', 'Permission to customize themes, logos, domains, and SSO.'),
]


ROLES = {
    # Platform Roles
    'platform_owner': {
        'name': 'Platform Owner',
        'description': 'Master global platform super-administrator with unrestricted access to all tenants and infrastructure.',
        'is_platform_role': True,
        'permissions': ['all'],
    },
    'platform_admin': {
        'name': 'Platform Administrator',
        'description': 'Global operations administrator for tenant monitoring, compliance, and platform operations.',
        'is_platform_role': True,
        'permissions': ['analytics.view', 'settings.view'],
    },

    # Institutional Roles
    'institution_owner': {
        'name': 'Institution Owner',
        'description': 'Primary institutional authority with complete control over tenant configuration, billing, and staff.',
        'is_platform_role': False,
        'permissions': ['all'],
    },
    'institution_admin': {
        'name': 'Institution Administrator',
        'description': 'Operational manager for institutional staff, academic policies, admissions, and settings.',
        'is_platform_role': False,
        'permissions': [
            'courses.view', 'courses.create', 'courses.edit', 'courses.publish',
            'members.view', 'members.invite', 'members.edit_role', 'members.suspend',
            'admissions.view', 'admissions.manage',
            'assessments.view', 'assessments.grade',
            'analytics.view',
            'settings.view', 'settings.edit',
        ],
    },
    'academic_admin': {
        'name': 'Academic Administrator',
        'description': 'Curriculum lead supervising courses, instructional content, faculty, and learning outcomes.',
        'is_platform_role': False,
        'permissions': [
            'courses.view', 'courses.create', 'courses.edit', 'courses.publish',
            'members.view',
            'assessments.view', 'assessments.grade',
            'analytics.view',
        ],
    },
    'instructor': {
        'name': 'Instructor / Faculty',
        'description': 'Educator creating lessons, delivering courses, interacting with students, and grading work.',
        'is_platform_role': False,
        'permissions': [
            'courses.view', 'courses.create', 'courses.edit',
            'assessments.view', 'assessments.grade',
        ],
    },
    'admissions_officer': {
        'name': 'Admissions Officer',
        'description': 'Registrar managing student intake, application reviews, and onboarding verification.',
        'is_platform_role': False,
        'permissions': [
            'admissions.view', 'admissions.manage',
            'members.view',
        ],
    },
    'learner': {
        'name': 'Learner / Student',
        'description': 'Enrolled student consuming educational materials, taking assessments, and earning credentials.',
        'is_platform_role': False,
        'permissions': [
            'courses.view',
        ],
    },
}


class Command(BaseCommand):
    help = 'Seeds initial standard permissions, institutional roles, and platform roles.'

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("Seeding permissions and roles..."))

        with transaction.atomic():
            perm_objects = {}
            for codename, name, module, description in PERMISSIONS:
                perm, created = Permission.objects.update_or_create(
                    codename=codename,
                    defaults={
                        'name': name,
                        'module': module,
                        'description': description,
                    }
                )
                perm_objects[codename] = perm

            self.stdout.write(self.style.SUCCESS(f"Provisioned {len(perm_objects)} system permissions."))

            all_perms = list(perm_objects.values())

            for slug, data in ROLES.items():
                role, created = Role.objects.update_or_create(
                    slug=slug,
                    defaults={
                        'name': data['name'],
                        'description': data['description'],
                        'is_platform_role': data['is_platform_role'],
                    }
                )

                # Clear previous mappings and re-assign
                RolePermission.objects.filter(role=role).delete()

                if 'all' in data['permissions']:
                    target_perms = all_perms
                else:
                    target_perms = [perm_objects[code] for code in data['permissions'] if code in perm_objects]

                role_perms = [
                    RolePermission(role=role, permission=p)
                    for p in target_perms
                ]
                RolePermission.objects.bulk_create(role_perms)

                self.stdout.write(
                    self.style.SUCCESS(f"Role '{role.name}' ({role.slug}) mapped to {len(target_perms)} permissions.")
                )

        self.stdout.write(self.style.SUCCESS("All standard permissions and roles seeded successfully."))
