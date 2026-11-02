from django.contrib import admin
from .models import (
    DiscussionThread,
    DiscussionReply,
    ThreadUpvote,
    Announcement,
    Notification,
)


class DiscussionReplyInline(admin.TabularInline):
    model = DiscussionReply
    extra = 1
    fields = ('author', 'content', 'upvotes_count', 'is_faculty_endorsed', 'created_at')
    readonly_fields = ('created_at',)


@admin.register(DiscussionThread)
class DiscussionThreadAdmin(admin.ModelAdmin):
    list_display = ('title', 'category', 'course', 'author', 'upvotes_count', 'is_pinned', 'created_at')
    list_filter = ('tenant', 'category', 'is_pinned', 'is_locked')
    search_fields = ('title', 'content', 'author__email')
    inlines = [DiscussionReplyInline]


@admin.register(DiscussionReply)
class DiscussionReplyAdmin(admin.ModelAdmin):
    list_display = ('author', 'thread', 'upvotes_count', 'is_faculty_endorsed', 'created_at')
    list_filter = ('tenant', 'is_faculty_endorsed')
    search_fields = ('content', 'author__email', 'thread__title')


@admin.register(Announcement)
class AnnouncementAdmin(admin.ModelAdmin):
    list_display = ('title', 'priority', 'target', 'author', 'tenant', 'is_published', 'published_at')
    list_filter = ('tenant', 'priority', 'target', 'is_published')
    search_fields = ('title', 'content')


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('recipient', 'notification_type', 'title', 'is_read', 'created_at')
    list_filter = ('tenant', 'notification_type', 'is_read')
    search_fields = ('recipient__email', 'title', 'message')
