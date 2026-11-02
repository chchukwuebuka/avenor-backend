import uuid
from django.core.management.base import BaseCommand
from django.utils import timezone
from apps.accounts.models import User
from apps.tenants.models import Tenant
from apps.courses.models import Course, Module, Lesson, CourseOffering
from apps.enrollments.models import Enrollment, LessonProgress, EnrollmentStatus
from apps.assessments.models import (
    Quiz,
    Question,
    QuestionOption,
    QuizAttempt,
    Assignment,
    AssignmentSubmission,
    Certificate,
)


class Command(BaseCommand):
    help = 'Seeds student enrollments, syllabus progress, quizzes, assignments, and verifiable certificates.'

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE('Seeding enrollments, assessments, and verifiable diplomas...'))

        northstar = Tenant.objects.filter(slug='northstar').first()
        apex = Tenant.objects.filter(slug='apex').first()

        if not northstar or not apex:
            self.stdout.write(self.style.ERROR('Northstar or Apex tenant not found. Run seed_courses first.'))
            return

        # 1. Ensure Demo Scholars Exist
        marcus, _ = User.objects.get_or_create(
            email='m.vance@northstar.avenor.edu',
            defaults={
                'first_name': 'Marcus',
                'last_name': 'Vance',
                'is_active': True,
            }
        )
        marcus.set_password('Password123!')
        marcus.save()

        elena, _ = User.objects.get_or_create(
            email='elena.rostova@apex.avenor.edu',
            defaults={
                'first_name': 'Elena',
                'last_name': 'Rostova',
                'is_active': True,
            }
        )
        elena.set_password('Password123!')
        elena.save()

        # 2. Enroll Marcus Vance in Full-Stack Systems Architecture
        fsa_offering = CourseOffering.objects.filter(tenant=northstar, course__slug='full-stack-systems-architecture').first()
        if fsa_offering:
            enr_marcus, _ = Enrollment.objects.get_or_create(
                tenant=northstar,
                student=marcus,
                offering=fsa_offering,
                defaults={
                    'status': EnrollmentStatus.ACTIVE,
                    'grade': 'A (93.5%)',
                }
            )

            # Pre-seed LessonProgress records
            fsa_lessons = Lesson.objects.filter(module__course=fsa_offering.course).order_by('order')
            for idx, lesson in enumerate(fsa_lessons):
                prog, _ = LessonProgress.objects.get_or_create(
                    tenant=northstar,
                    enrollment=enr_marcus,
                    lesson=lesson
                )
                # Complete the first 4 lessons (67% progress)
                if idx < 4:
                    prog.is_completed = True
                    prog.completed_at = timezone.now()
                    prog.time_spent_seconds = 1800
                    prog.save()

            enr_marcus.recalculate_progress()

            # 3. Create Quiz for FSA Course
            quiz, _ = Quiz.objects.get_or_create(
                tenant=northstar,
                course=fsa_offering.course,
                title='Multi-Tenant Architecture & RLS Knowledge Check',
                defaults={
                    'description': 'Assess mastery of PostgreSQL row-level security, tenant isolation, and connection pooling.',
                    'passing_score_percentage': 80,
                    'time_limit_minutes': 20,
                    'max_attempts': 3,
                    'order': 1,
                }
            )

            # Quiz Questions & Options
            q1, _ = Question.objects.get_or_create(
                tenant=northstar,
                quiz=quiz,
                prompt='Which PostgreSQL feature guarantees row-level data segregation across tenant schemas without application-level where filters?',
                defaults={
                    'points': 10,
                    'order': 1,
                    'explanation': 'Row-Level Security (RLS) dynamically applies filtering policies at the database engine level based on session variables.'
                }
            )
            if not q1.options.exists():
                QuestionOption.objects.create(question=q1, text='Foreign Key Constraints', is_correct=False, order=1)
                QuestionOption.objects.create(question=q1, text='Row-Level Security (CREATE POLICY)', is_correct=True, order=2)
                QuestionOption.objects.create(question=q1, text='Trigger Procedures', is_correct=False, order=3)
                QuestionOption.objects.create(question=q1, text='Table Partitioning', is_correct=False, order=4)

            q2, _ = Question.objects.get_or_create(
                tenant=northstar,
                quiz=quiz,
                prompt='What is the primary benefit of maintaining an abstract TenantModel base in Django?',
                defaults={
                    'points': 10,
                    'order': 2,
                    'explanation': 'It guarantees every child entity automatically inherits a tenant foreign key and scoped manager filtering.'
                }
            )
            if not q2.options.exists():
                QuestionOption.objects.create(question=q2, text='Enforces automatic foreign keys and isolated QuerySet managers', is_correct=True, order=1)
                QuestionOption.objects.create(question=q2, text='Reduces SQL query caching overhead', is_correct=False, order=2)
                QuestionOption.objects.create(question=q2, text='Enables multi-threading in Celery workers', is_correct=False, order=3)

            # Quiz Attempt for Marcus
            correct_opt_1 = q1.options.filter(is_correct=True).first()
            correct_opt_2 = q2.options.filter(is_correct=True).first()
            attempt, _ = QuizAttempt.objects.get_or_create(
                tenant=northstar,
                enrollment=enr_marcus,
                quiz=quiz,
                attempt_number=1,
                defaults={
                    'score': 20,
                    'max_score': 20,
                    'score_percentage': 100.00,
                    'is_passed': True,
                    'completed_at': timezone.now(),
                    'answers_payload': {
                        str(q1.id): str(correct_opt_1.id) if correct_opt_1 else '',
                        str(q2.id): str(correct_opt_2.id) if correct_opt_2 else '',
                    }
                }
            )

            # 4. Create Practical Laboratory Assignment
            assignment, _ = Assignment.objects.get_or_create(
                tenant=northstar,
                course=fsa_offering.course,
                title='Lab 2.3: Multi-Tenant Database Partitioning Engine',
                defaults={
                    'prompt': 'Implement a dynamic PostgreSQL table partitioner that generates weekly chunks with tenant hash keys.',
                    'max_points': 100,
                    'rubric_criteria': [
                        {'title': 'Correctness of RLS Policies', 'max_points': 40},
                        {'title': 'Partition Pruning Performance', 'max_points': 30},
                        {'title': 'Automated Test Coverage', 'max_points': 30},
                    ],
                    'due_days_after_start': 14,
                }
            )

            # Assignment Submission for Marcus
            AssignmentSubmission.objects.get_or_create(
                tenant=northstar,
                enrollment=enr_marcus,
                assignment=assignment,
                defaults={
                    'submission_url': 'https://github.com/marcusvance/avenor-pg-partitioning',
                    'notes': 'Implemented declarative hash partitioning with benchmark test suite demonstrating zero query leakage.',
                    'grade_points': 98.00,
                    'feedback': 'Exceptional engineering quality. Partition pruning reduces sequential scans to under 2ms.',
                    'graded_at': timezone.now(),
                }
            )

            self.stdout.write(self.style.SUCCESS(f"Seeded FSA enrollment, quiz, and lab for Marcus Vance ({enr_marcus.progress_percentage}%)."))

        # 5. Enroll Elena Rostova in Machine Learning in Production (100% completed)
        ml_offering = CourseOffering.objects.filter(tenant=apex, course__slug='machine-learning-in-production').first()
        if ml_offering:
            enr_elena, _ = Enrollment.objects.get_or_create(
                tenant=apex,
                student=elena,
                offering=ml_offering,
                defaults={
                    'status': EnrollmentStatus.COMPLETED,
                    'grade': 'A+ (97.8%)',
                    'completed_at': timezone.now(),
                    'progress_percentage': 100,
                }
            )

            ml_lessons = Lesson.objects.filter(module__course=ml_offering.course)
            for lesson in ml_lessons:
                LessonProgress.objects.get_or_create(
                    tenant=apex,
                    enrollment=enr_elena,
                    lesson=lesson,
                    defaults={
                        'is_completed': True,
                        'completed_at': timezone.now(),
                        'time_spent_seconds': 2400,
                    }
                )

            # Confer Verified Certificate for Elena Rostova
            cert_hash = Certificate.generate_verification_hash(
                apex.slug,
                elena.email,
                ml_offering.offering_code,
                '20260220120000'
            )
            Certificate.objects.get_or_create(
                tenant=apex,
                enrollment=enr_elena,
                defaults={
                    'certificate_number': 'AVN-CERT-2026-MLA-771829',
                    'verification_hash': cert_hash,
                    'recipient_name': 'Elena Rostova',
                    'course_title': ml_offering.course.title,
                    'grade': 'Pass with Highest Distinction (A+)',
                    'metadata': {
                        'dean_signature': 'Dr. Marcus Vance, Visiting Scholar',
                        'registrar_signature': 'Sophia Laurent',
                        'cumulative_gpa': '4.00',
                        'credits_conferred': 4,
                    }
                }
            )
            self.stdout.write(self.style.SUCCESS(f"Conferred verified certificate for Elena Rostova: AVN-CERT-2026-MLA-771829"))

        self.stdout.write(self.style.SUCCESS('Successfully seeded all enrollments, assessments, and diplomas.'))
