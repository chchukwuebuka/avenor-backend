from django.contrib import admin
from .models import Programme, Course, Module, Lesson, CourseOffering


class LessonInline(admin.TabularInline):
    model = Lesson
    extra = 1


class ModuleInline(admin.StackedInline):
    model = Module
    extra = 1


class CourseOfferingInline(admin.TabularInline):
    model = CourseOffering
    extra = 1


@admin.register(Programme)
class ProgrammeAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'tenant', 'status', 'created_at')
    list_filter = ('status', 'tenant')
    search_fields = ('name', 'slug', 'tenant__name')


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ('title', 'slug', 'programme', 'tenant', 'level', 'status', 'duration')
    list_filter = ('status', 'level', 'tenant')
    search_fields = ('title', 'slug', 'tenant__name')
    inlines = [ModuleInline, CourseOfferingInline]


@admin.register(Module)
class ModuleAdmin(admin.ModelAdmin):
    list_display = ('title', 'course', 'order', 'tenant')
    list_filter = ('tenant',)
    search_fields = ('title', 'course__title')
    inlines = [LessonInline]


@admin.register(Lesson)
class LessonAdmin(admin.ModelAdmin):
    list_display = ('title', 'module', 'lesson_type', 'duration_minutes', 'order', 'is_preview')
    list_filter = ('lesson_type', 'is_preview', 'tenant')
    search_fields = ('title', 'module__title')


@admin.register(CourseOffering)
class CourseOfferingAdmin(admin.ModelAdmin):
    list_display = ('offering_code', 'cohort_name', 'course', 'tenant', 'start_date', 'price', 'currency', 'status')
    list_filter = ('status', 'delivery_mode', 'tenant')
    search_fields = ('offering_code', 'cohort_name', 'course__title')
