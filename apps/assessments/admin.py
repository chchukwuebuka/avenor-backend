from django.contrib import admin
from .models import (
    Quiz,
    Question,
    QuestionOption,
    QuizAttempt,
    Assignment,
    AssignmentSubmission,
    Certificate,
)


class QuestionOptionInline(admin.TabularInline):
    model = QuestionOption
    extra = 4


class QuestionInline(admin.TabularInline):
    model = Question
    extra = 1
    fields = ('order', 'prompt', 'points')


@admin.register(Quiz)
class QuizAdmin(admin.ModelAdmin):
    list_display = ('title', 'course', 'tenant', 'passing_score_percentage', 'time_limit_minutes', 'max_attempts')
    list_filter = ('tenant', 'course')
    search_fields = ('title', 'course__title')
    inlines = [QuestionInline]


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ('prompt', 'quiz', 'points', 'order')
    list_filter = ('quiz__tenant', 'quiz')
    inlines = [QuestionOptionInline]


@admin.register(QuizAttempt)
class QuizAttemptAdmin(admin.ModelAdmin):
    list_display = ('enrollment', 'quiz', 'score', 'max_score', 'score_percentage', 'is_passed', 'completed_at')
    list_filter = ('is_passed', 'tenant')
    search_fields = ('enrollment__student__email', 'quiz__title')


@admin.register(Assignment)
class AssignmentAdmin(admin.ModelAdmin):
    list_display = ('title', 'course', 'tenant', 'max_points', 'due_days_after_start')
    list_filter = ('tenant', 'course')
    search_fields = ('title', 'course__title')


@admin.register(AssignmentSubmission)
class AssignmentSubmissionAdmin(admin.ModelAdmin):
    list_display = ('enrollment', 'assignment', 'grade_points', 'submitted_at', 'graded_at', 'graded_by')
    list_filter = ('tenant', 'assignment')
    search_fields = ('enrollment__student__email', 'assignment__title')


@admin.register(Certificate)
class CertificateAdmin(admin.ModelAdmin):
    list_display = ('certificate_number', 'recipient_name', 'course_title', 'tenant', 'issued_at')
    list_filter = ('tenant',)
    search_fields = ('certificate_number', 'recipient_name', 'verification_hash')
    readonly_fields = ('verification_hash', 'issued_at')
