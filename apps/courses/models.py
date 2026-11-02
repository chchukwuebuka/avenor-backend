import uuid
from django.db import models
from apps.tenants.models import Tenant, TenantModel, TenantManager


class AcademicStatus(models.TextChoices):
    DRAFT = 'draft', 'Draft'
    PUBLISHED = 'published', 'Published'
    ARCHIVED = 'archived', 'Archived'


class Programme(TenantModel):
    """
    Academic programme or department under which courses are organized.
    E.g. "Executive Leadership", "Financial Engineering".
    """
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='programmes')
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=100, db_index=True)
    description = models.TextField(blank=True, default='')
    image = models.CharField(max_length=500, blank=True, default='')
    status = models.CharField(
        max_length=20,
        choices=AcademicStatus.choices,
        default=AcademicStatus.DRAFT
    )

    class Meta:
        verbose_name = 'Programme'
        verbose_name_plural = 'Programmes'
        unique_together = ('tenant', 'slug')
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.tenant.slug})"


class CourseLevel(models.TextChoices):
    BEGINNER = 'beginner', 'Beginner'
    INTERMEDIATE = 'intermediate', 'Intermediate'
    ADVANCED = 'advanced', 'Advanced'


class Course(TenantModel):
    """
    Primary educational course entity belonging to a specific Tenant.
    """
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='courses')
    programme = models.ForeignKey(
        Programme,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='courses'
    )
    title = models.CharField(max_length=255)
    slug = models.SlugField(max_length=100, db_index=True)
    short_description = models.CharField(max_length=500)
    full_description = models.TextField(blank=True, default='')
    learning_objectives = models.JSONField(default=list, blank=True)
    requirements = models.JSONField(default=list, blank=True)
    duration = models.CharField(max_length=50, default='8 Weeks')
    level = models.CharField(
        max_length=20,
        choices=CourseLevel.choices,
        default=CourseLevel.BEGINNER
    )
    status = models.CharField(
        max_length=20,
        choices=AcademicStatus.choices,
        default=AcademicStatus.DRAFT,
        db_index=True
    )
    course_image = models.CharField(max_length=500, blank=True, default='')

    class Meta:
        verbose_name = 'Course'
        verbose_name_plural = 'Courses'
        unique_together = ('tenant', 'slug')
        ordering = ['title']
        indexes = [
            models.Index(fields=['tenant', 'status', 'slug']),
        ]

    def __str__(self):
        return f"{self.title} ({self.tenant.slug})"


class Module(TenantModel):
    """
    Syllabus module/unit within a course.
    """
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='course_modules')
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='modules')
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, default='')
    order = models.PositiveIntegerField(default=1)

    class Meta:
        verbose_name = 'Course Module'
        verbose_name_plural = 'Course Modules'
        ordering = ['order', 'created_at']
        unique_together = ('course', 'order')

    def __str__(self):
        return f"{self.course.title} - Module {self.order}: {self.title}"


class LessonType(models.TextChoices):
    ARTICLE = 'article', 'Article / Reading'
    VIDEO = 'video', 'Video Lecture'
    QUIZ = 'quiz', 'Quiz / Knowledge Check'
    ASSIGNMENT = 'assignment', 'Assignment / Submission'
    EXTERNAL_LINK = 'external_link', 'External Resource'


class Lesson(TenantModel):
    """
    Individual lesson or instructional topic within a Module.
    """
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='lessons')
    module = models.ForeignKey(Module, on_delete=models.CASCADE, related_name='lessons')
    title = models.CharField(max_length=255)
    lesson_type = models.CharField(
        max_length=30,
        choices=LessonType.choices,
        default=LessonType.ARTICLE
    )
    content = models.TextField(blank=True, default='')
    duration_minutes = models.PositiveIntegerField(default=15)
    order = models.PositiveIntegerField(default=1)
    is_preview = models.BooleanField(default=False)

    class Meta:
        verbose_name = 'Lesson'
        verbose_name_plural = 'Lessons'
        ordering = ['order', 'created_at']
        unique_together = ('module', 'order')

    def __str__(self):
        return f"{self.module.title} - Lesson {self.order}: {self.title}"


class DeliveryMode(models.TextChoices):
    ONLINE = 'online', 'Online'
    PHYSICAL = 'physical', 'Physical Classroom'
    HYBRID = 'hybrid', 'Hybrid'
    SELF_PACED = 'self_paced', 'Self-Paced'


class CohortStatus(models.TextChoices):
    DRAFT = 'draft', 'Draft'
    OPEN = 'open', 'Open for Enrolment'
    CLOSED = 'closed', 'Enrolment Closed'
    IN_PROGRESS = 'in_progress', 'Cohort In Progress'
    COMPLETED = 'completed', 'Completed'
    CANCELLED = 'cancelled', 'Cancelled'


class CourseOffering(TenantModel):
    """
    Specific academic intake / cohort of a Course with schedule, pricing, and capacity.
    """
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='cohorts')
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='offerings')
    offering_code = models.CharField(max_length=50, db_index=True)
    cohort_name = models.CharField(max_length=255)
    start_date = models.DateField()
    end_date = models.DateField()
    application_deadline = models.DateField(null=True, blank=True)
    capacity = models.PositiveIntegerField(default=50)
    price = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    currency = models.CharField(max_length=10, default='USD')
    delivery_mode = models.CharField(
        max_length=30,
        choices=DeliveryMode.choices,
        default=DeliveryMode.ONLINE
    )
    status = models.CharField(
        max_length=30,
        choices=CohortStatus.choices,
        default=CohortStatus.OPEN,
        db_index=True
    )

    class Meta:
        verbose_name = 'Course Cohort Offering'
        verbose_name_plural = 'Course Cohort Offerings'
        unique_together = ('tenant', 'offering_code')
        ordering = ['-start_date']

    def __str__(self):
        return f"{self.course.title} ({self.offering_code})"
