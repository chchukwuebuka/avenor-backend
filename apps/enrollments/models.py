import uuid
from django.db import models
from django.utils import timezone
from apps.tenants.models import Tenant, TenantModel
from apps.accounts.models import User
from apps.courses.models import CourseOffering, Lesson


class EnrollmentStatus(models.TextChoices):
    ENROLLED = 'enrolled', 'Enrolled'
    ACTIVE = 'active', 'Active'
    COMPLETED = 'completed', 'Completed'
    SUSPENDED = 'suspended', 'Suspended'
    DROPPED = 'dropped', 'Dropped'


class Enrollment(TenantModel):
    """
    Represents an admitted scholar's binding to an institutional CourseOffering cohort.
    Tracks academic standing, continuous progress, and graduation conferral.
    """
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        related_name='enrollments'
    )
    student = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='enrollments'
    )
    offering = models.ForeignKey(
        CourseOffering,
        on_delete=models.CASCADE,
        related_name='enrollments'
    )
    status = models.CharField(
        max_length=20,
        choices=EnrollmentStatus.choices,
        default=EnrollmentStatus.ACTIVE,
        db_index=True
    )
    enrolled_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    grade = models.CharField(max_length=30, blank=True, default='')
    progress_percentage = models.PositiveSmallIntegerField(default=0)
    last_accessed_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Enrollment'
        verbose_name_plural = 'Enrollments'
        unique_together = ('student', 'offering')
        ordering = ['-enrolled_at']
        indexes = [
            models.Index(fields=['tenant', 'status']),
            models.Index(fields=['student', 'status']),
        ]

    def __str__(self):
        return f"{self.student.email} -> {self.offering.offering_code} ({self.status})"

    def recalculate_progress(self):
        """
        Recalculates completion percentage based on total lessons in the course curriculum.
        """
        total_lessons = Lesson.objects.filter(module__course=self.offering.course).count()
        if total_lessons == 0:
            self.progress_percentage = 0
            self.save(update_fields=['progress_percentage', 'last_accessed_at'])
            return 0

        completed_lessons = self.lesson_progress.filter(is_completed=True).count()
        percentage = min(100, int((completed_lessons / total_lessons) * 100))
        self.progress_percentage = percentage

        if percentage >= 100 and not self.completed_at:
            self.completed_at = timezone.now()
            self.status = EnrollmentStatus.COMPLETED

        self.save(update_fields=['progress_percentage', 'completed_at', 'status', 'last_accessed_at'])
        return percentage


class LessonProgress(TenantModel):
    """
    Granular instructional tracking record per lesson for an enrolled scholar.
    """
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        related_name='lesson_progress_records'
    )
    enrollment = models.ForeignKey(
        Enrollment,
        on_delete=models.CASCADE,
        related_name='lesson_progress'
    )
    lesson = models.ForeignKey(
        Lesson,
        on_delete=models.CASCADE,
        related_name='student_progress_records'
    )
    is_completed = models.BooleanField(default=False)
    completed_at = models.DateTimeField(null=True, blank=True)
    time_spent_seconds = models.PositiveIntegerField(default=0)
    last_accessed_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Lesson Progress'
        verbose_name_plural = 'Lesson Progress Records'
        unique_together = ('enrollment', 'lesson')
        ordering = ['lesson__order']

    def __str__(self):
        status_icon = '✓' if self.is_completed else '○'
        return f"[{status_icon}] {self.enrollment.student.email} - {self.lesson.title}"

    def mark_completed(self):
        self.is_completed = True
        self.completed_at = timezone.now()
        self.save(update_fields=['is_completed', 'completed_at', 'last_accessed_at'])
        self.enrollment.recalculate_progress()

    def mark_incomplete(self):
        self.is_completed = False
        self.completed_at = None
        self.save(update_fields=['is_completed', 'completed_at', 'last_accessed_at'])
        self.enrollment.recalculate_progress()
