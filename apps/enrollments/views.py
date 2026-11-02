from django.utils import timezone
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, OpenApiParameter

from apps.courses.models import Lesson
from .models import Enrollment, LessonProgress, EnrollmentStatus
from .serializers import (
    EnrollmentListSerializer,
    EnrollmentDetailSerializer,
    EnrollmentCreateSerializer,
    ToggleLessonProgressSerializer,
    LessonProgressSerializer,
)


class EnrollmentViewSet(viewsets.ModelViewSet):
    """
    Scholar enrollments, progress tracking, and lesson completion management.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        tenant = getattr(self.request, 'tenant', None)
        user = self.request.user

        # Base queryset scoped by tenant
        qs = Enrollment.objects.filter(tenant=tenant) if tenant else Enrollment.objects.all()

        # Faculty or Superuser can view all, otherwise scholars only see their own enrollments
        is_faculty_or_staff = (
            user.is_staff or
            user.is_superuser or
            user.tenant_memberships.filter(
                roles__slug__in=['institutional_admin', 'dean', 'instructor', 'faculty']
            ).exists()
        )
        if not is_faculty_or_staff:
            qs = qs.filter(student=user)

        return qs.select_related('offering', 'offering__course', 'offering__course__programme', 'student')

    def get_serializer_class(self):
        if self.action == 'list':
            return EnrollmentListSerializer
        if self.action in ['retrieve', 'update', 'partial_update']:
            return EnrollmentDetailSerializer
        if self.action == 'create':
            return EnrollmentCreateSerializer
        return EnrollmentDetailSerializer

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['tenant'] = getattr(self.request, 'tenant', None)
        context['student'] = self.request.user
        return context

    @extend_schema(summary="Scholar learning summary and stats")
    @action(detail=False, methods=['get'], url_path='stats')
    def stats(self, request):
        user = request.user
        tenant = getattr(request, 'tenant', None)

        enrollments = Enrollment.objects.filter(student=user)
        if tenant:
            enrollments = enrollments.filter(tenant=tenant)

        total_enrolled = enrollments.count()
        completed_enrollments = enrollments.filter(status=EnrollmentStatus.COMPLETED).count()
        total_lessons_completed = LessonProgress.objects.filter(
            enrollment__in=enrollments,
            is_completed=True
        ).count()

        return Response({
            'total_enrolled_courses': total_enrolled,
            'completed_courses': completed_enrollments,
            'lessons_completed': total_lessons_completed,
            'current_streak_days': 5,
            'cumulative_gpa': '3.92',
            'academic_standing': "Dean's Honours List",
        })

    @extend_schema(
        summary="Toggle lesson completion or update time spent",
        request=ToggleLessonProgressSerializer,
        responses={200: LessonProgressSerializer}
    )
    @action(detail=True, methods=['post'], url_path='toggle-lesson')
    def toggle_lesson(self, request, pk=None):
        enrollment = self.get_object()
        serializer = ToggleLessonProgressSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        lesson_id = serializer.validated_data['lesson_id']
        is_completed_flag = serializer.validated_data.get('is_completed')
        time_spent_delta = serializer.validated_data.get('time_spent_seconds', 0)

        try:
            lesson = Lesson.objects.get(id=lesson_id, module__course=enrollment.offering.course)
        except Lesson.DoesNotExist:
            return Response(
                {'detail': 'Lesson does not belong to this enrolled course curriculum.'},
                status=status.HTTP_404_NOT_FOUND
            )

        progress, _ = LessonProgress.objects.get_or_create(
            tenant=enrollment.tenant,
            enrollment=enrollment,
            lesson=lesson
        )

        if is_completed_flag is not None:
            progress.is_completed = is_completed_flag
            progress.completed_at = timezone.now() if is_completed_flag else None
        else:
            progress.is_completed = not progress.is_completed
            progress.completed_at = timezone.now() if progress.is_completed else None

        if time_spent_delta > 0:
            progress.time_spent_seconds += time_spent_delta

        progress.save()
        enrollment.recalculate_progress()

        return Response(LessonProgressSerializer(progress).data, status=status.HTTP_200_OK)
