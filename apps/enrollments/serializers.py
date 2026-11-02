from rest_framework import serializers
from apps.courses.models import CourseOffering, Course, Module, Lesson
from apps.courses.serializers import CourseOfferingSerializer
from apps.accounts.serializers import UserSerializer
from .models import Enrollment, LessonProgress, EnrollmentStatus


class LessonProgressSerializer(serializers.ModelSerializer):
    lesson_id = serializers.UUIDField(source='lesson.id', read_only=True)
    lesson_title = serializers.CharField(source='lesson.title', read_only=True)
    lesson_type = serializers.CharField(source='lesson.lesson_type', read_only=True)
    duration_minutes = serializers.IntegerField(source='lesson.duration_minutes', read_only=True)

    class Meta:
        model = LessonProgress
        fields = [
            'id',
            'lesson_id',
            'lesson_title',
            'lesson_type',
            'duration_minutes',
            'is_completed',
            'completed_at',
            'time_spent_seconds',
            'last_accessed_at',
        ]
        read_only_fields = ['id', 'completed_at', 'last_accessed_at']


class EnrollmentListSerializer(serializers.ModelSerializer):
    course_title = serializers.CharField(source='offering.course.title', read_only=True)
    course_slug = serializers.CharField(source='offering.course.slug', read_only=True)
    course_id = serializers.UUIDField(source='offering.course.id', read_only=True)
    programme_name = serializers.CharField(source='offering.course.programme.name', read_only=True, default='')
    cohort_name = serializers.CharField(source='offering.cohort_name', read_only=True)
    offering_code = serializers.CharField(source='offering.offering_code', read_only=True)
    delivery_mode = serializers.CharField(source='offering.delivery_mode', read_only=True)
    tenant_slug = serializers.CharField(source='tenant.slug', read_only=True)

    class Meta:
        model = Enrollment
        fields = [
            'id',
            'course_id',
            'course_title',
            'course_slug',
            'programme_name',
            'cohort_name',
            'offering_code',
            'delivery_mode',
            'tenant_slug',
            'status',
            'progress_percentage',
            'grade',
            'enrolled_at',
            'completed_at',
            'last_accessed_at',
        ]
        read_only_fields = fields


class EnrollmentDetailSerializer(serializers.ModelSerializer):
    course = serializers.SerializerMethodField()
    offering = CourseOfferingSerializer(read_only=True)
    student = UserSerializer(read_only=True)
    lesson_progress = LessonProgressSerializer(many=True, read_only=True)
    total_lessons_count = serializers.SerializerMethodField()
    completed_lessons_count = serializers.SerializerMethodField()

    class Meta:
        model = Enrollment
        fields = [
            'id',
            'tenant',
            'student',
            'course',
            'offering',
            'status',
            'progress_percentage',
            'grade',
            'total_lessons_count',
            'completed_lessons_count',
            'enrolled_at',
            'completed_at',
            'last_accessed_at',
            'lesson_progress',
        ]
        read_only_fields = fields

    def get_course(self, obj):
        course = obj.offering.course
        return {
            'id': str(course.id),
            'title': course.title,
            'slug': course.slug,
            'short_description': course.short_description,
            'level': course.level,
            'duration': course.duration,
            'programme_name': course.programme.name if course.programme else '',
        }

    def get_total_lessons_count(self, obj):
        return Lesson.objects.filter(module__course=obj.offering.course).count()

    def get_completed_lessons_count(self, obj):
        return obj.lesson_progress.filter(is_completed=True).count()


class EnrollmentCreateSerializer(serializers.ModelSerializer):
    offering_id = serializers.UUIDField(write_only=True)

    class Meta:
        model = Enrollment
        fields = ['offering_id']

    def validate_offering_id(self, value):
        tenant = self.context.get('tenant')
        try:
            offering = CourseOffering.objects.get(id=value, tenant=tenant)
        except CourseOffering.DoesNotExist:
            raise serializers.ValidationError("Cohort offering does not exist for this institution.")
        return value

    def create(self, validated_data):
        tenant = self.context.get('tenant')
        student = self.context.get('student')
        offering = CourseOffering.objects.get(id=validated_data['offering_id'], tenant=tenant)

        enrollment, created = Enrollment.objects.get_or_create(
            tenant=tenant,
            student=student,
            offering=offering,
            defaults={'status': EnrollmentStatus.ACTIVE}
        )

        # Pre-seed empty LessonProgress records for all lessons in the course
        lessons = Lesson.objects.filter(module__course=offering.course)
        for lesson in lessons:
            LessonProgress.objects.get_or_create(
                tenant=tenant,
                enrollment=enrollment,
                lesson=lesson
            )

        return enrollment


class ToggleLessonProgressSerializer(serializers.Serializer):
    lesson_id = serializers.UUIDField()
    is_completed = serializers.BooleanField(required=False, default=None)
    time_spent_seconds = serializers.IntegerField(required=False, default=0)
