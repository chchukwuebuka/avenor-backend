from datetime import date, timedelta
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework import status
from apps.accounts.models import User
from apps.tenants.models import Tenant
from apps.courses.models import Programme, Course, Module, Lesson, CourseOffering, AcademicStatus
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


class AssessmentModelAndAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()

        # Tenant
        self.tenant = Tenant.objects.create(
            name="Meridian Tech",
            slug="meridian-test",
            contact_email="registrar@meridian.test"
        )

        # Student User
        self.student = User.objects.create_user(
            email="scholar@meridian.test",
            password="Password123!",
            first_name="Jordan",
            last_name="Lee"
        )

        # Faculty User
        self.faculty = User.objects.create_user(
            email="prof@meridian.test",
            password="Password123!",
            first_name="Prof",
            last_name="Vance",
            is_staff=True
        )

        # Course & Offering
        self.prog = Programme.objects.create(
            tenant=self.tenant,
            name="Systems Engineering",
            slug="systems-eng"
        )
        self.course = Course.objects.create(
            tenant=self.tenant,
            programme=self.prog,
            title="Distributed Systems",
            slug="distributed-systems",
            short_description="Distributed consensus and Raft",
            status=AcademicStatus.PUBLISHED
        )
        self.module = Module.objects.create(
            tenant=self.tenant,
            course=self.course,
            title="Consensus Protocols",
            order=1
        )
        self.lesson = Lesson.objects.create(
            tenant=self.tenant,
            module=self.module,
            title="Raft Algorithm Mechanics",
            order=1
        )

        self.offering = CourseOffering.objects.create(
            tenant=self.tenant,
            course=self.course,
            offering_code="DS-2026-01",
            cohort_name="Spring 2026",
            start_date=date.today(),
            end_date=date.today() + timedelta(days=90),
            status="open"
        )

        self.enrollment = Enrollment.objects.create(
            tenant=self.tenant,
            student=self.student,
            offering=self.offering,
            status=EnrollmentStatus.ACTIVE,
            progress_percentage=85
        )

    def test_quiz_auto_grading_evaluation(self):
        quiz = Quiz.objects.create(
            tenant=self.tenant,
            course=self.course,
            lesson=self.lesson,
            title="Raft Leader Election Quiz",
            passing_score_percentage=75,
            max_attempts=3
        )

        q1 = Question.objects.create(
            tenant=self.tenant,
            quiz=quiz,
            prompt="What triggers a Raft follower to initiate an election?",
            points=10,
            order=1
        )
        opt_wrong = QuestionOption.objects.create(question=q1, text="Leader heartbeat received", is_correct=False, order=1)
        opt_correct = QuestionOption.objects.create(question=q1, text="Election timeout expires without heartbeat", is_correct=True, order=2)

        attempt = QuizAttempt.objects.create(
            tenant=self.tenant,
            enrollment=self.enrollment,
            quiz=quiz
        )

        # 1. Evaluate with correct answer
        score_pct = attempt.evaluate({str(q1.id): str(opt_correct.id)})
        self.assertEqual(score_pct, 100.0)
        self.assertTrue(attempt.is_passed)
        self.assertEqual(attempt.score, 10)
        self.assertEqual(attempt.max_score, 10)

        # Lesson progress should be marked completed
        prog = LessonProgress.objects.get(enrollment=self.enrollment, lesson=self.lesson)
        self.assertTrue(prog.is_completed)

    def test_submit_quiz_api_endpoint(self):
        quiz = Quiz.objects.create(
            tenant=self.tenant,
            course=self.course,
            title="Consensus Quiz",
            passing_score_percentage=50,
            max_attempts=1
        )
        q1 = Question.objects.create(tenant=self.tenant, quiz=quiz, prompt="Test Q", points=10)
        opt = QuestionOption.objects.create(question=q1, text="Right", is_correct=True)

        self.client.force_authenticate(user=self.student)
        url = f"/api/v1/assessments/quizzes/{quiz.id}/submit/"

        response = self.client.post(url, {
            'enrollment_id': str(self.enrollment.id),
            'answers': {str(q1.id): str(opt.id)}
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['score'], 10)
        self.assertTrue(response.data['is_passed'])

        # Second attempt should be rejected because max_attempts=1
        response_second = self.client.post(url, {
            'enrollment_id': str(self.enrollment.id),
            'answers': {str(q1.id): str(opt.id)}
        }, format='json')
        self.assertEqual(response_second.status_code, status.HTTP_400_BAD_REQUEST)

    def test_assignment_submission_and_faculty_grading(self):
        assignment = Assignment.objects.create(
            tenant=self.tenant,
            course=self.course,
            lesson=self.lesson,
            title="Lab: Implement Raft Log Replication",
            max_points=100
        )

        # Student submits assignment
        self.client.force_authenticate(user=self.student)
        url = f"/api/v1/assessments/assignments/{assignment.id}/submit/"
        resp = self.client.post(url, {
            'enrollment_id': str(self.enrollment.id),
            'submission_url': 'https://github.com/scholar/raft-engine',
            'notes': 'All tests in cluster simulation pass.'
        }, format='json')

        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        sub_id = resp.data['id']

        # Faculty grades assignment
        self.client.force_authenticate(user=self.faculty)
        grade_url = f"/api/v1/assessments/assignments/{assignment.id}/grade/"
        resp_grade = self.client.post(grade_url, {
            'submission_id': sub_id,
            'grade_points': 95.00,
            'feedback': 'Excellent state machine handling.'
        }, format='json')

        self.assertEqual(resp_grade.status_code, status.HTTP_200_OK)
        self.assertEqual(resp_grade.data['grade_points'], '95.00')

    def test_certificate_conferral_and_public_verification(self):
        # 1. Confer Certificate via API
        self.client.force_authenticate(user=self.student)
        confer_url = "/api/v1/assessments/certificates/confer/"

        # Enrollment has progress 85% >= 80%
        resp = self.client.post(confer_url, {'enrollment_id': str(self.enrollment.id)}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)

        cert_number = resp.data['certificate_number']
        cert_hash = resp.data['verification_hash']
        self.assertTrue(cert_hash)

        # 2. Public Verification without authentication
        self.client.force_authenticate(user=None)
        verify_url = f"/api/v1/assessments/certificates/verify/{cert_hash}/"
        resp_verify = self.client.get(verify_url)

        self.assertEqual(resp_verify.status_code, status.HTTP_200_OK)
        self.assertTrue(resp_verify.data['is_valid'])
        self.assertEqual(resp_verify.data['certificate_number'], cert_number)
        self.assertEqual(resp_verify.data['recipient_name'], "Jordan Lee")
        self.assertEqual(resp_verify.data['institution_name'], "Meridian Tech")

        # 3. Invalid Hash returns 404
        resp_fake = self.client.get("/api/v1/assessments/certificates/verify/invalid-hash-12345/")
        self.assertEqual(resp_fake.status_code, status.HTTP_404_NOT_FOUND)
        self.assertFalse(resp_fake.data['is_valid'])
