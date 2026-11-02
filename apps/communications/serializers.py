from rest_framework import serializers
from apps.courses.models import Course, Lesson, CourseOffering
from apps.accounts.serializers import UserSerializer
from .models import (
    DiscussionThread,
    DiscussionReply,
    ThreadUpvote,
    Announcement,
    Notification,
    DiscussionCategory,
    AnnouncementPriority,
)


class DiscussionReplySerializer(serializers.ModelSerializer):
    author_name = serializers.SerializerMethodField()
    author_role = serializers.SerializerMethodField()
    child_replies = serializers.SerializerMethodField()

    class Meta:
        model = DiscussionReply
        fields = [
            'id',
            'author',
            'author_name',
            'author_role',
            'parent_reply',
            'content',
            'upvotes_count',
            'is_faculty_endorsed',
            'created_at',
            'child_replies',
        ]
        read_only_fields = ['id', 'author', 'author_name', 'author_role', 'upvotes_count', 'is_faculty_endorsed', 'created_at']

    def get_author_name(self, obj):
        name = f"{obj.author.first_name} {obj.author.last_name}".strip()
        return name if name else obj.author.email

    def get_author_role(self, obj):
        if obj.author.is_staff or obj.author.is_superuser:
            return 'Faculty Lecturer'
        if obj.author.tenant_memberships.filter(roles__slug__in=['dean', 'faculty', 'instructor']).exists():
            return 'Faculty Instructor'
        return 'Enrolled Scholar'

    def get_child_replies(self, obj):
        # Only nest one level deep to avoid recursion loops
        if obj.parent_reply is None:
            children = obj.child_replies.all()
            return DiscussionReplySerializer(children, many=True, context=self.context).data
        return []


class DiscussionReplyCreateSerializer(serializers.ModelSerializer):
    parent_reply_id = serializers.UUIDField(required=False, allow_null=True)

    class Meta:
        model = DiscussionReply
        fields = ['content', 'parent_reply_id']


class DiscussionThreadListSerializer(serializers.ModelSerializer):
    author_name = serializers.SerializerMethodField()
    author_role = serializers.SerializerMethodField()
    course_title = serializers.CharField(source='course.title', read_only=True)
    replies_count = serializers.IntegerField(source='replies.count', read_only=True)

    class Meta:
        model = DiscussionThread
        fields = [
            'id',
            'category',
            'title',
            'course',
            'course_title',
            'lesson',
            'author_name',
            'author_role',
            'upvotes_count',
            'replies_count',
            'is_pinned',
            'is_locked',
            'created_at',
            'updated_at',
        ]
        read_only_fields = fields

    def get_author_name(self, obj):
        name = f"{obj.author.first_name} {obj.author.last_name}".strip()
        return name if name else obj.author.email

    def get_author_role(self, obj):
        if obj.author.is_staff or obj.author.is_superuser:
            return 'Faculty Lecturer'
        if obj.author.tenant_memberships.filter(roles__slug__in=['dean', 'faculty', 'instructor']).exists():
            return 'Faculty Instructor'
        return 'Enrolled Scholar'


class DiscussionThreadDetailSerializer(serializers.ModelSerializer):
    author_name = serializers.SerializerMethodField()
    author_role = serializers.SerializerMethodField()
    course_title = serializers.CharField(source='course.title', read_only=True)
    replies = serializers.SerializerMethodField()
    has_upvoted = serializers.SerializerMethodField()

    class Meta:
        model = DiscussionThread
        fields = [
            'id',
            'category',
            'title',
            'content',
            'course',
            'course_title',
            'lesson',
            'offering',
            'author',
            'author_name',
            'author_role',
            'upvotes_count',
            'has_upvoted',
            'is_pinned',
            'is_locked',
            'created_at',
            'updated_at',
            'replies',
        ]
        read_only_fields = fields

    def get_author_name(self, obj):
        name = f"{obj.author.first_name} {obj.author.last_name}".strip()
        return name if name else obj.author.email

    def get_author_role(self, obj):
        if obj.author.is_staff or obj.author.is_superuser:
            return 'Faculty Lecturer'
        if obj.author.tenant_memberships.filter(roles__slug__in=['dean', 'faculty', 'instructor']).exists():
            return 'Faculty Instructor'
        return 'Enrolled Scholar'

    def get_replies(self, obj):
        top_level_replies = obj.replies.filter(parent_reply__isnull=True).select_related('author').prefetch_related('child_replies')
        return DiscussionReplySerializer(top_level_replies, many=True, context=self.context).data

    def get_has_upvoted(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return obj.upvotes.filter(user=request.user).exists()
        return False


class DiscussionThreadCreateSerializer(serializers.ModelSerializer):
    course_id = serializers.UUIDField(write_only=True)
    lesson_id = serializers.UUIDField(required=False, allow_null=True, write_only=True)
    offering_id = serializers.UUIDField(required=False, allow_null=True, write_only=True)

    class Meta:
        model = DiscussionThread
        fields = [
            'id',
            'category',
            'title',
            'content',
            'course_id',
            'lesson_id',
            'offering_id',
        ]
        read_only_fields = ['id']

    def create(self, validated_data):
        tenant = self.context.get('tenant')
        author = self.context.get('author')
        course = Course.objects.get(id=validated_data['course_id'])
        tenant = tenant or course.tenant
        
        lesson = None
        if validated_data.get('lesson_id'):
            lesson = Lesson.objects.filter(id=validated_data['lesson_id'], module__course=course).first()

        offering = None
        if validated_data.get('offering_id'):
            offering = CourseOffering.objects.filter(id=validated_data['offering_id'], course=course).first()

        thread = DiscussionThread.objects.create(
            tenant=tenant,
            author=author,
            course=course,
            lesson=lesson,
            offering=offering,
            category=validated_data.get('category', DiscussionCategory.GENERAL),
            title=validated_data['title'],
            content=validated_data['content'],
        )
        return thread


class AnnouncementSerializer(serializers.ModelSerializer):
    author_name = serializers.SerializerMethodField()
    course_title = serializers.CharField(source='course.title', read_only=True)

    class Meta:
        model = Announcement
        fields = [
            'id',
            'title',
            'content',
            'priority',
            'target',
            'course',
            'course_title',
            'offering',
            'author_name',
            'is_published',
            'published_at',
            'created_at',
        ]
        read_only_fields = ['id', 'author_name', 'created_at']

    def get_author_name(self, obj):
        name = f"{obj.author.first_name} {obj.author.last_name}".strip()
        return name if name else obj.author.email


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = [
            'id',
            'notification_type',
            'title',
            'message',
            'action_url',
            'is_read',
            'read_at',
            'created_at',
        ]
        read_only_fields = fields
