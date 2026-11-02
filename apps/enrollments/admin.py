from django.contrib import admin
from .models import Enrollment, LessonProgress


class LessonProgressInline(admin.TabularInline):
    model = LessonProgress
    extra = 0
    fields = ('lesson', 'is_completed', 'completed_at', 'time_spent_seconds')
    readonly_fields = ('completed_at',)


@admin.register(Enrollment)
class EnrollmentAdmin(admin.ModelAdmin):
    list_display = ('student', 'offering', 'tenant', 'status', 'progress_percentage', 'grade', 'enrolled_at')
    list_filter = ('tenant', 'status')
    search_fields = ('student__email', 'offering__offering_code', 'offering__course__title')
    inlines = [LessonProgressInline]


@admin.register(LessonProgress)
class LessonProgressAdmin(admin.ModelAdmin):
    list_display = ('enrollment', 'lesson', 'is_completed', 'time_spent_seconds', 'completed_at')
    list_filter = ('is_completed', 'tenant')
    search_fields = ('enrollment__student__email', 'lesson__title')
