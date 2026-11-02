import uuid
from django.utils import timezone
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, OpenApiParameter

from apps.enrollments.models import Enrollment, EnrollmentStatus
from .models import (
    Quiz,
    QuizAttempt,
    Assignment,
    AssignmentSubmission,
    Certificate,
)
from .serializers import (
    QuizListSerializer,
    QuizDetailSerializer,
    QuizSubmitSerializer,
    QuizAttemptSerializer,
    AssignmentSerializer,
    AssignmentSubmissionSerializer,
    AssignmentGradeSerializer,
    CertificateSerializer,
)


class QuizViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Modular assessment quizzes, question pools, and auto-evaluated student attempts.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        tenant = getattr(self.request, 'tenant', None)
        course_id = self.request.query_params.get('course_id')

        qs = Quiz.objects.filter(tenant=tenant) if tenant else Quiz.objects.all()
        if course_id:
            qs = qs.filter(course_id=course_id)
        return qs.prefetch_related('questions', 'questions__options')

    def get_serializer_class(self):
        if self.action == 'list':
            return QuizListSerializer
        return QuizDetailSerializer

    @extend_schema(
        summary="Submit answers for automated quiz evaluation",
        request=QuizSubmitSerializer,
        responses={201: QuizAttemptSerializer}
    )
    @action(detail=True, methods=['post'], url_path='submit')
    def submit_quiz(self, request, pk=None):
        quiz = self.get_object()
        serializer = QuizSubmitSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        enrollment_id = serializer.validated_data['enrollment_id']
        answers = serializer.validated_data['answers']

        try:
            enrollment = Enrollment.objects.get(
                id=enrollment_id,
                student=request.user,
                offering__course=quiz.course
            )
        except Enrollment.DoesNotExist:
            return Response(
                {'detail': 'Valid active enrollment matching this quiz was not found.'},
                status=status.HTTP_404_NOT_FOUND
            )

        prior_attempts_count = QuizAttempt.objects.filter(
            enrollment=enrollment,
            quiz=quiz
        ).count()

        if prior_attempts_count >= quiz.max_attempts:
            return Response(
                {'detail': f'Maximum attempts ({quiz.max_attempts}) reached for this assessment.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        attempt = QuizAttempt.objects.create(
            tenant=quiz.tenant,
            enrollment=enrollment,
            quiz=quiz,
            attempt_number=prior_attempts_count + 1
        )
        attempt.evaluate(answers)

        return Response(QuizAttemptSerializer(attempt).data, status=status.HTTP_201_CREATED)

    @extend_schema(summary="List student attempts for this quiz")
    @action(detail=True, methods=['get'], url_path='attempts')
    def attempts(self, request, pk=None):
        quiz = self.get_object()
        attempts = QuizAttempt.objects.filter(
            quiz=quiz,
            enrollment__student=request.user
        ).order_by('-started_at')
        return Response(QuizAttemptSerializer(attempts, many=True).data)


class AssignmentViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Hands-on practical laboratory assignments and submission desk.
    """
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = AssignmentSerializer

    def get_queryset(self):
        tenant = getattr(self.request, 'tenant', None)
        course_id = self.request.query_params.get('course_id')

        qs = Assignment.objects.filter(tenant=tenant) if tenant else Assignment.objects.all()
        if course_id:
            qs = qs.filter(course_id=course_id)
        return qs

    @extend_schema(summary="Submit practical laboratory assignment deliverable")
    @action(detail=True, methods=['post'], url_path='submit')
    def submit_assignment(self, request, pk=None):
        assignment = self.get_object()
        enrollment_id = request.data.get('enrollment_id')
        submission_url = request.data.get('submission_url', '')
        notes = request.data.get('notes', '')

        try:
            enrollment = Enrollment.objects.get(
                id=enrollment_id,
                student=request.user,
                offering__course=assignment.course
            )
        except Enrollment.DoesNotExist:
            return Response(
                {'detail': 'Matching active enrollment not found.'},
                status=status.HTTP_404_NOT_FOUND
            )

        submission, created = AssignmentSubmission.objects.update_or_create(
            tenant=assignment.tenant,
            enrollment=enrollment,
            assignment=assignment,
            defaults={
                'submission_url': submission_url,
                'notes': notes,
                'submitted_at': timezone.now()
            }
        )

        return Response(
            AssignmentSubmissionSerializer(submission).data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK
        )

    @extend_schema(summary="Grade laboratory submission (Faculty/Admin only)")
    @action(detail=True, methods=['post'], url_path='grade')
    def grade_submission(self, request, pk=None):
        is_faculty = (
            request.user.is_staff or
            request.user.is_superuser or
            request.user.tenant_memberships.filter(
                roles__slug__in=['institutional_admin', 'dean', 'instructor', 'faculty']
            ).exists()
        )
        if not is_faculty:
            return Response({'detail': 'Faculty permissions required to grade.'}, status=status.HTTP_403_FORBIDDEN)

        assignment = self.get_object()
        submission_id = request.data.get('submission_id')
        serializer = AssignmentGradeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            submission = AssignmentSubmission.objects.get(id=submission_id, assignment=assignment)
        except AssignmentSubmission.DoesNotExist:
            return Response({'detail': 'Submission not found.'}, status=status.HTTP_404_NOT_FOUND)

        submission.grade_points = serializer.validated_data['grade_points']
        submission.feedback = serializer.validated_data.get('feedback', '')
        submission.graded_by = request.user
        submission.graded_at = timezone.now()
        submission.save()

        # If assignment is tied to a lesson, mark lesson completed
        if assignment.lesson:
            from apps.enrollments.models import LessonProgress
            progress, _ = LessonProgress.objects.get_or_create(
                tenant=assignment.tenant,
                enrollment=submission.enrollment,
                lesson=assignment.lesson
            )
            progress.mark_completed()

        return Response(AssignmentSubmissionSerializer(submission).data, status=status.HTTP_200_OK)


class CertificateViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Issued cryptographic diplomas and public verification desk.
    """
    serializer_class = CertificateSerializer

    def get_permissions(self):
        if self.action in ['verify']:
            return [permissions.AllowAny()]
        return [permissions.IsAuthenticated()]

    def get_queryset(self):
        tenant = getattr(self.request, 'tenant', None)
        user = self.request.user

        qs = Certificate.objects.filter(tenant=tenant) if tenant else Certificate.objects.all()
        is_faculty_or_staff = (
            user.is_staff or
            user.is_superuser or
            user.tenant_memberships.filter(
                roles__slug__in=['institutional_admin', 'dean', 'instructor', 'faculty']
            ).exists()
        )
        if not is_faculty_or_staff:
            qs = qs.filter(enrollment__student=user)
        return qs.select_related('tenant', 'enrollment', 'enrollment__student')

    @extend_schema(summary="Public cryptographic diploma verification endpoint")
    @action(detail=False, methods=['get'], url_path='verify/(?P<hash>[^/.]+)')
    def verify(self, request, hash=None):
        try:
            cert = Certificate.objects.select_related('tenant', 'enrollment', 'enrollment__student').get(verification_hash=hash)
        except Certificate.DoesNotExist:
            return Response(
                {
                    'is_valid': False,
                    'message': 'Cryptographic certificate record could not be found or has been revoked.',
                    'verification_hash': hash,
                },
                status=status.HTTP_404_NOT_FOUND
            )

        return Response({
            'is_valid': True,
            'certificate_number': cert.certificate_number,
            'verification_hash': cert.verification_hash,
            'recipient_name': cert.recipient_name,
            'course_title': cert.course_title,
            'grade': cert.grade,
            'institution_name': cert.tenant.name,
            'institution_slug': cert.tenant.slug,
            'issued_at': cert.issued_at.isoformat(),
            'metadata': cert.metadata,
        }, status=status.HTTP_200_OK)

    @extend_schema(summary="Confer official diploma upon academic progress completion")
    @action(detail=False, methods=['post'], url_path='confer')
    def confer(self, request):
        enrollment_id = request.data.get('enrollment_id')
        try:
            enrollment = Enrollment.objects.select_related('tenant', 'student', 'offering__course').get(
                id=enrollment_id,
                student=request.user
            )
        except Enrollment.DoesNotExist:
            return Response({'detail': 'Enrollment record not found.'}, status=status.HTTP_404_NOT_FOUND)

        if enrollment.progress_percentage < 80:
            return Response(
                {'detail': f'Minimum 80% curriculum progress required (current: {enrollment.progress_percentage}%).'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if hasattr(enrollment, 'certificate'):
            return Response(CertificateSerializer(enrollment.certificate).data, status=status.HTTP_200_OK)

        timestamp_str = timezone.now().strftime('%Y%m%d%H%M%S')
        cert_num = f"AVN-CERT-{timezone.now().year}-{enrollment.offering.offering_code.upper()[:3]}-{uuid.uuid4().hex[:6].upper()}"
        hash_digest = Certificate.generate_verification_hash(
            enrollment.tenant.slug,
            enrollment.student.email,
            enrollment.offering.offering_code,
            timestamp_str
        )

        cert = Certificate.objects.create(
            tenant=enrollment.tenant,
            enrollment=enrollment,
            certificate_number=cert_num,
            verification_hash=hash_digest,
            recipient_name=f"{enrollment.student.first_name} {enrollment.student.last_name}".strip() or enrollment.student.email,
            course_title=enrollment.offering.course.title,
            grade=enrollment.grade or 'Pass with Distinction',
            metadata={
                'dean_signature': 'Prof. Alistair Thorne, Ph.D.',
                'registrar_signature': 'David K. Mensah',
                'cumulative_gpa': '3.92',
                'credits_conferred': 4,
            }
        )

        return Response(CertificateSerializer(cert).data, status=status.HTTP_201_CREATED)
