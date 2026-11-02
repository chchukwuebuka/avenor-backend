from rest_framework import serializers
from .models import Programme, Course, Module, Lesson, CourseOffering, CourseLevel, DeliveryMode, AcademicStatus


class ProgrammeSerializer(serializers.ModelSerializer):
    courses_count = serializers.SerializerMethodField()

    class Meta:
        model = Programme
        fields = [
            'id',
            'name',
            'slug',
            'description',
            'image',
            'status',
            'courses_count',
            'created_at',
        ]
        read_only_fields = ['id', 'courses_count', 'created_at']

    def get_courses_count(self, obj):
        try:
            return obj.courses.filter(status=AcademicStatus.PUBLISHED).count()
        except Exception:
            return 0


class LessonSerializer(serializers.ModelSerializer):
    class Meta:
        model = Lesson
        fields = [
            'id',
            'module',
            'title',
            'lesson_type',
            'content',
            'duration_minutes',
            'order',
            'is_preview',
            'created_at',
        ]
        read_only_fields = ['id', 'module', 'created_at']


class ModuleSerializer(serializers.ModelSerializer):
    lessons = LessonSerializer(many=True, read_only=True)
    lessons_count = serializers.SerializerMethodField()
    total_duration_minutes = serializers.SerializerMethodField()

    class Meta:
        model = Module
        fields = [
            'id',
            'course',
            'title',
            'description',
            'order',
            'lessons',
            'lessons_count',
            'total_duration_minutes',
            'created_at',
        ]
        read_only_fields = ['id', 'course', 'lessons', 'lessons_count', 'total_duration_minutes', 'created_at']

    def get_lessons_count(self, obj):
        return obj.lessons.count()

    def get_total_duration_minutes(self, obj):
        return sum(obj.lessons.values_list('duration_minutes', flat=True))


class CourseOfferingSerializer(serializers.ModelSerializer):
    is_open = serializers.SerializerMethodField()

    class Meta:
        model = CourseOffering
        fields = [
            'id',
            'course',
            'offering_code',
            'cohort_name',
            'start_date',
            'end_date',
            'application_deadline',
            'capacity',
            'price',
            'currency',
            'delivery_mode',
            'status',
            'is_open',
            'created_at',
        ]
        read_only_fields = ['id', 'course', 'is_open', 'created_at']

    def get_is_open(self, obj):
        return obj.status == 'open'


class PublicCourseListSerializer(serializers.ModelSerializer):
    programme_name = serializers.CharField(source='programme.name', read_only=True, default='')
    programme_slug = serializers.CharField(source='programme.slug', read_only=True, default='')
    active_cohorts = serializers.SerializerMethodField()
    tuition_display = serializers.SerializerMethodField()

    class Meta:
        model = Course
        fields = [
            'id',
            'title',
            'slug',
            'programme_name',
            'programme_slug',
            'short_description',
            'duration',
            'level',
            'status',
            'course_image',
            'active_cohorts',
            'tuition_display',
            'created_at',
        ]
        read_only_fields = fields

    def get_active_cohorts(self, obj):
        return obj.offerings.filter(status='open').count()

    def get_tuition_display(self, obj):
        primary_cohort = obj.offerings.filter(status='open').first() or obj.offerings.first()
        if primaryCohort := primary_cohort:
            return {
                'price': float(primaryCohort.price),
                'currency': primaryCohort.currency,
                'delivery_mode': primaryCohort.delivery_mode,
            }
        return {'price': 0.0, 'currency': 'USD', 'delivery_mode': 'online'}


class PublicCourseDetailSerializer(serializers.ModelSerializer):
    programme = ProgrammeSerializer(read_only=True)
    modules = ModuleSerializer(many=True, read_only=True)
    offerings = CourseOfferingSerializer(many=True, read_only=True)

    class Meta:
        model = Course
        fields = [
            'id',
            'title',
            'slug',
            'programme',
            'short_description',
            'full_description',
            'learning_objectives',
            'requirements',
            'duration',
            'level',
            'status',
            'course_image',
            'modules',
            'offerings',
            'created_at',
            'updated_at',
        ]
        read_only_fields = fields


class CourseCreateUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Course
        fields = [
            'id',
            'programme',
            'title',
            'slug',
            'short_description',
            'full_description',
            'learning_objectives',
            'requirements',
            'duration',
            'level',
            'status',
            'course_image',
        ]
        read_only_fields = ['id']

    def validate_slug(self, value):
        tenant = self.context.get('tenant')
        cleaned = value.lower().strip()
        qs = Course.objects.filter(tenant=tenant, slug=cleaned)
        if self.instance:
            qs = qs.exclude(id=self.instance.id)
        if qs.exists():
            raise serializers.ValidationError("A course with this slug already exists in this institution.")
        return cleaned
