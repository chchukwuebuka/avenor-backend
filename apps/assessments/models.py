import uuid
import hashlib
from django.db import models
from django.utils import timezone
from apps.tenants.models import Tenant, TenantModel
from apps.accounts.models import User
from apps.courses.models import Course, Lesson


class Quiz(TenantModel):
    """
    Formative or summative knowledge assessment tied to a Course or Lesson.
    """
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='quizzes')
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='quizzes')
    lesson = models.ForeignKey(
        Lesson,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='quizzes'
    )
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, default='')
    passing_score_percentage = models.PositiveSmallIntegerField(default=75)
    time_limit_minutes = models.PositiveIntegerField(default=20)
    max_attempts = models.PositiveSmallIntegerField(default=3)
    order = models.PositiveIntegerField(default=1)

    class Meta:
        verbose_name = 'Quiz'
        verbose_name_plural = 'Quizzes'
        ordering = ['order', 'created_at']

    def __str__(self):
        return f"{self.title} ({self.course.title})"


class Question(TenantModel):
    """
    Multiple choice question within an assessment Quiz.
    """
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='quiz_questions')
    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name='questions')
    prompt = models.TextField()
    explanation = models.TextField(
        blank=True,
        default='',
        help_text='Detailed pedagogical reasoning revealed upon submission.'
    )
    points = models.PositiveIntegerField(default=10)
    order = models.PositiveIntegerField(default=1)

    class Meta:
        verbose_name = 'Question'
        verbose_name_plural = 'Questions'
        ordering = ['order', 'created_at']

    def __str__(self):
        return f"Q{self.order}: {self.prompt[:60]}"


class QuestionOption(models.Model):
    """
    Selectable choice for a multiple-choice question.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name='options')
    text = models.CharField(max_length=500)
    is_correct = models.BooleanField(default=False)
    order = models.PositiveIntegerField(default=1)

    class Meta:
        verbose_name = 'Question Option'
        verbose_name_plural = 'Question Options'
        ordering = ['order']

    def __str__(self):
        return f"{'[✓]' if self.is_correct else '[ ]'} {self.text[:50]}"


class QuizAttempt(TenantModel):
    """
    Student execution attempt on a Quiz with answers and automated score evaluation.
    """
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='quiz_attempts')
    enrollment = models.ForeignKey(
        'enrollments.Enrollment',
        on_delete=models.CASCADE,
        related_name='quiz_attempts'
    )
    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name='attempts')
    attempt_number = models.PositiveSmallIntegerField(default=1)
    score = models.PositiveIntegerField(default=0)
    max_score = models.PositiveIntegerField(default=0)
    score_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)
    is_passed = models.BooleanField(default=False)
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    answers_payload = models.JSONField(
        default=dict,
        blank=True,
        help_text='Map of question_id to selected option_id'
    )

    class Meta:
        verbose_name = 'Quiz Attempt'
        verbose_name_plural = 'Quiz Attempts'
        ordering = ['-started_at']

    def __str__(self):
        return f"{self.enrollment.student.email} - {self.quiz.title} ({self.score_percentage}%)"

    def evaluate(self, answers_dict):
        """
        Auto-grades student answers against correct QuestionOptions.
        answers_dict: {str(question_id): str(option_id)}
        """
        self.answers_payload = answers_dict
        total_score = 0
        max_possible = 0

        questions = self.quiz.questions.all().prefetch_related('options')
        for question in questions:
            max_possible += question.points
            selected_option_id = answers_dict.get(str(question.id))
            if selected_option_id:
                correct_option = question.options.filter(is_correct=True).first()
                if correct_option and str(correct_option.id) == str(selected_option_id):
                    total_score += question.points

        self.score = total_score
        self.max_score = max_possible
        self.score_percentage = round((total_score / max_possible * 100), 2) if max_possible > 0 else 0.00
        self.is_passed = self.score_percentage >= self.quiz.passing_score_percentage
        self.completed_at = timezone.now()
        self.save()

        # If passed and associated with a lesson, mark that lesson completed
        if self.is_passed and self.quiz.lesson:
            from apps.enrollments.models import LessonProgress
            progress, _ = LessonProgress.objects.get_or_create(
                tenant=self.tenant,
                enrollment=self.enrollment,
                lesson=self.quiz.lesson
            )
            progress.mark_completed()

        return self.score_percentage


class Assignment(TenantModel):
    """
    Practical or laboratory assignment requiring project submission (GitHub, documentation).
    """
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='assignments')
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='assignments')
    lesson = models.ForeignKey(
        Lesson,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assignments'
    )
    title = models.CharField(max_length=255)
    prompt = models.TextField()
    rubric_criteria = models.JSONField(
        default=list,
        blank=True,
        help_text='List of evaluation criteria with max points'
    )
    max_points = models.PositiveIntegerField(default=100)
    due_days_after_start = models.PositiveIntegerField(default=14)

    class Meta:
        verbose_name = 'Assignment'
        verbose_name_plural = 'Assignments'
        ordering = ['created_at']

    def __str__(self):
        return f"{self.title} ({self.course.title})"


class AssignmentSubmission(TenantModel):
    """
    Scholar's laboratory deliverable submission with instructor grading and rubric feedback.
    """
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='assignment_submissions')
    enrollment = models.ForeignKey(
        'enrollments.Enrollment',
        on_delete=models.CASCADE,
        related_name='assignment_submissions'
    )
    assignment = models.ForeignKey(Assignment, on_delete=models.CASCADE, related_name='submissions')
    submission_url = models.URLField(max_length=500, blank=True, default='')
    notes = models.TextField(blank=True, default='')
    submitted_at = models.DateTimeField(auto_now_add=True)
    grade_points = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    feedback = models.TextField(blank=True, default='')
    graded_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='graded_assignments'
    )
    graded_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'Assignment Submission'
        verbose_name_plural = 'Assignment Submissions'
        unique_together = ('enrollment', 'assignment')
        ordering = ['-submitted_at']

    def __str__(self):
        return f"{self.enrollment.student.email} -> {self.assignment.title}"


class Certificate(TenantModel):
    """
    Tamper-evident cryptographically verifiable academic completion diploma.
    """
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='certificates')
    enrollment = models.OneToOneField(
        'enrollments.Enrollment',
        on_delete=models.CASCADE,
        related_name='certificate'
    )
    certificate_number = models.CharField(max_length=100, unique=True, db_index=True)
    verification_hash = models.CharField(max_length=128, unique=True, db_index=True)
    recipient_name = models.CharField(max_length=255)
    course_title = models.CharField(max_length=255)
    grade = models.CharField(max_length=50, blank=True, default='')
    issued_at = models.DateTimeField(auto_now_add=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        verbose_name = 'Certificate'
        verbose_name_plural = 'Certificates'
        ordering = ['-issued_at']

    def __str__(self):
        return f"Certificate: {self.certificate_number} -> {self.recipient_name}"

    @classmethod
    def generate_verification_hash(cls, tenant_slug, student_email, course_code, timestamp_str):
        raw_token = f"{tenant_slug}:{student_email}:{course_code}:{timestamp_str}:AVENOR_EDTECH_V1"
        return hashlib.sha256(raw_token.encode('utf-8')).hexdigest()
