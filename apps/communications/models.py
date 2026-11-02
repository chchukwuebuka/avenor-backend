import uuid
from django.db import models
from django.utils import timezone
from apps.tenants.models import Tenant, TenantModel
from apps.accounts.models import User
from apps.courses.models import Course, Lesson, CourseOffering


class DiscussionCategory(models.TextChoices):
    LECTURE_QA = 'lecture_qa', 'Lecture Q&A'
    ASSIGNMENT_HELP = 'assignment_help', 'Lab & Assignment Help'
    GENERAL = 'general', 'General Discourse'
    ANNOUNCEMENT = 'announcement', 'Announcement'


class DiscussionThread(TenantModel):
    """
    Cohort and course-level technical discussion thread.
    """
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='discussion_threads')
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='discussion_threads')
    lesson = models.ForeignKey(
        Lesson,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='discussion_threads'
    )
    offering = models.ForeignKey(
        CourseOffering,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='discussion_threads'
    )
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name='discussion_threads')
    category = models.CharField(
        max_length=30,
        choices=DiscussionCategory.choices,
        default=DiscussionCategory.GENERAL,
        db_index=True
    )
    title = models.CharField(max_length=255)
    content = models.TextField()
    upvotes_count = models.PositiveIntegerField(default=0)
    is_pinned = models.BooleanField(default=False)
    is_locked = models.BooleanField(default=False)

    class Meta:
        verbose_name = 'Discussion Thread'
        verbose_name_plural = 'Discussion Threads'
        ordering = ['-is_pinned', '-created_at']

    def __str__(self):
        return f"[{self.category}] {self.title[:50]} by {self.author.email}"


class DiscussionReply(TenantModel):
    """
    Peer or faculty reply within a DiscussionThread, supporting threaded nesting.
    """
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='discussion_replies')
    thread = models.ForeignKey(DiscussionThread, on_delete=models.CASCADE, related_name='replies')
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name='discussion_replies')
    parent_reply = models.ForeignKey(
        'self',
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name='child_replies'
    )
    content = models.TextField()
    upvotes_count = models.PositiveIntegerField(default=0)
    is_faculty_endorsed = models.BooleanField(default=False)

    class Meta:
        verbose_name = 'Discussion Reply'
        verbose_name_plural = 'Discussion Replies'
        ordering = ['created_at']

    def __str__(self):
        return f"Reply by {self.author.email} on {self.thread.title[:30]}"


class ThreadUpvote(models.Model):
    """
    Tracks unique upvotes per user on discussion threads.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    thread = models.ForeignKey(DiscussionThread, on_delete=models.CASCADE, related_name='upvotes')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='thread_upvotes')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Thread Upvote'
        verbose_name_plural = 'Thread Upvotes'
        unique_together = ('thread', 'user')

    def __str__(self):
        return f"{self.user.email} -> {self.thread.title[:30]}"


class AnnouncementPriority(models.TextChoices):
    LOW = 'low', 'Low'
    NORMAL = 'normal', 'Normal'
    HIGH = 'high', 'High'
    URGENT = 'urgent', 'Urgent'


class AnnouncementTarget(models.TextChoices):
    ALL_INSTITUTION = 'all_institution', 'Entire Institution'
    SPECIFIC_COURSE = 'specific_course', 'Specific Course'
    SPECIFIC_COHORT = 'specific_cohort', 'Specific Cohort Offering'


class Announcement(TenantModel):
    """
    Official institutional or faculty bulletin broadcasted to cohorts.
    """
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='announcements')
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name='authored_announcements')
    course = models.ForeignKey(
        Course,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name='announcements'
    )
    offering = models.ForeignKey(
        CourseOffering,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name='announcements'
    )
    title = models.CharField(max_length=255)
    content = models.TextField()
    priority = models.CharField(
        max_length=20,
        choices=AnnouncementPriority.choices,
        default=AnnouncementPriority.NORMAL
    )
    target = models.CharField(
        max_length=30,
        choices=AnnouncementTarget.choices,
        default=AnnouncementTarget.ALL_INSTITUTION
    )
    is_published = models.BooleanField(default=True)
    published_at = models.DateTimeField(default=timezone.now)

    class Meta:
        verbose_name = 'Announcement'
        verbose_name_plural = 'Announcements'
        ordering = ['-published_at']

    def __str__(self):
        return f"[{self.priority.upper()}] {self.title}"


class NotificationType(models.TextChoices):
    DISCUSSION_REPLY = 'discussion_reply', 'Discussion Reply'
    ASSIGNMENT_GRADED = 'assignment_graded', 'Assignment Graded'
    CERTIFICATE_ISSUED = 'certificate_issued', 'Certificate Conferred'
    ANNOUNCEMENT_PUBLISHED = 'announcement_published', 'New Announcement'
    ENROLLMENT_CONFIRMED = 'enrollment_confirmed', 'Enrollment Confirmed'


class Notification(TenantModel):
    """
    In-app notification dispatch for enrolled scholars and faculty.
    """
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='notifications')
    recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    notification_type = models.CharField(max_length=40, choices=NotificationType.choices)
    title = models.CharField(max_length=255)
    message = models.TextField()
    action_url = models.CharField(max_length=500, blank=True, default='')
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'Notification'
        verbose_name_plural = 'Notifications'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.recipient.email} - {self.title} ({'Read' if self.is_read else 'Unread'})"

    def mark_as_read(self):
        self.is_read = True
        self.read_at = timezone.now()
        self.save(update_fields=['is_read', 'read_at', 'updated_at'])
