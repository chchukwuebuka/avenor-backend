from django.utils import timezone
from rest_framework import viewsets, status, permissions
from rest_framework.exceptions import PermissionDenied
from rest_framework.decorators import action
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, OpenApiParameter

from .models import (
    DiscussionThread,
    DiscussionReply,
    ThreadUpvote,
    Announcement,
    Notification,
    DiscussionCategory,
)
from .serializers import (
    DiscussionThreadListSerializer,
    DiscussionThreadDetailSerializer,
    DiscussionThreadCreateSerializer,
    DiscussionReplySerializer,
    DiscussionReplyCreateSerializer,
    AnnouncementSerializer,
    NotificationSerializer,
)


def is_faculty_or_staff(user):
    return (
        user.is_staff or
        user.is_superuser or
        user.tenant_memberships.filter(
            roles__slug__in=['institutional_admin', 'dean', 'instructor', 'faculty']
        ).exists()
    )


class DiscussionThreadViewSet(viewsets.ModelViewSet):
    """
    Cohort and course colloquium discussion threads with threaded replies and upvoting.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        tenant = getattr(self.request, 'tenant', None)
        course_id = self.request.query_params.get('course_id')
        category = self.request.query_params.get('category')

        qs = DiscussionThread.objects.filter(tenant=tenant) if tenant else DiscussionThread.objects.all()
        if course_id:
            qs = qs.filter(course_id=course_id)
        if category and category != 'all':
            qs = qs.filter(category=category)

        return qs.select_related('author', 'course', 'lesson', 'offering').prefetch_related('replies')

    def get_serializer_class(self):
        if self.action == 'list':
            return DiscussionThreadListSerializer
        if self.action == 'create':
            return DiscussionThreadCreateSerializer
        return DiscussionThreadDetailSerializer

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['tenant'] = getattr(self.request, 'tenant', None)
        context['author'] = self.request.user
        return context

    @extend_schema(summary="Post reply to discussion thread", request=DiscussionReplyCreateSerializer)
    @action(detail=True, methods=['post'], url_path='reply')
    def add_reply(self, request, pk=None):
        thread = self.get_object()
        if thread.is_locked:
            return Response({'detail': 'This discussion thread has been locked by faculty.'}, status=status.HTTP_400_BAD_REQUEST)

        serializer = DiscussionReplyCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        parent_reply = None
        parent_id = serializer.validated_data.get('parent_reply_id')
        if parent_id:
            parent_reply = DiscussionReply.objects.filter(id=parent_id, thread=thread).first()

        is_endorsed = is_faculty_or_staff(request.user)

        reply = DiscussionReply.objects.create(
            tenant=thread.tenant,
            thread=thread,
            author=request.user,
            parent_reply=parent_reply,
            content=serializer.validated_data['content'],
            is_faculty_endorsed=is_endorsed
        )

        # Notify thread author if someone else replies
        if thread.author != request.user:
            Notification.objects.create(
                tenant=thread.tenant,
                recipient=thread.author,
                notification_type='discussion_reply',
                title=f"New reply on '{thread.title[:30]}...'",
                message=f"{request.user.email} replied: {reply.content[:80]}",
                action_url=f"/community?thread={thread.id}"
            )

        return Response(DiscussionReplySerializer(reply, context={'request': request}).data, status=status.HTTP_201_CREATED)

    @extend_schema(summary="Toggle upvote on discussion thread")
    @action(detail=True, methods=['post'], url_path='upvote')
    def toggle_upvote(self, request, pk=None):
        thread = self.get_object()
        user = request.user

        upvote = ThreadUpvote.objects.filter(thread=thread, user=user).first()
        if upvote:
            upvote.delete()
            thread.upvotes_count = max(0, thread.upvotes_count - 1)
            has_upvoted = False
        else:
            ThreadUpvote.objects.create(thread=thread, user=user)
            thread.upvotes_count += 1
            has_upvoted = True

        thread.save(update_fields=['upvotes_count'])
        return Response({
            'upvotes_count': thread.upvotes_count,
            'has_upvoted': has_upvoted,
        }, status=status.HTTP_200_OK)

    @extend_schema(summary="Toggle pinned status (Faculty only)")
    @action(detail=True, methods=['post'], url_path='pin')
    def toggle_pin(self, request, pk=None):
        if not is_faculty_or_staff(request.user):
            return Response({'detail': 'Faculty permissions required to pin.'}, status=status.HTTP_403_FORBIDDEN)

        thread = self.get_object()
        thread.is_pinned = not thread.is_pinned
        thread.save(update_fields=['is_pinned'])
        return Response({'is_pinned': thread.is_pinned}, status=status.HTTP_200_OK)


class AnnouncementViewSet(viewsets.ModelViewSet):
    """
    Institutional announcements and cohort broadcasts.
    """
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = AnnouncementSerializer

    def get_queryset(self):
        tenant = getattr(self.request, 'tenant', None)
        qs = Announcement.objects.filter(tenant=tenant) if tenant else Announcement.objects.all()

        # Regular scholars only see published announcements
        if not is_faculty_or_staff(self.request.user):
            qs = qs.filter(is_published=True)

        return qs.select_related('author', 'course', 'offering')

    def perform_create(self, serializer):
        if not is_faculty_or_staff(self.request.user):
            raise PermissionDenied("Only faculty and staff can create official announcements.")

        tenant = getattr(self.request, 'tenant', None)
        if not tenant:
            course = serializer.validated_data.get('course')
            if course:
                tenant = course.tenant
            else:
                membership = self.request.user.tenant_memberships.first()
                if membership:
                    tenant = membership.tenant
                else:
                    from apps.tenants.models import Tenant
                    tenant = Tenant.objects.first()

        serializer.save(tenant=tenant, author=self.request.user)


class NotificationViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Scholar notifications and reading status.
    """
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = NotificationSerializer

    def get_queryset(self):
        return Notification.objects.filter(recipient=self.request.user).order_by('-created_at')

    @extend_schema(summary="Mark notification as read")
    @action(detail=True, methods=['post'], url_path='read')
    def mark_read(self, request, pk=None):
        notification = self.get_object()
        notification.mark_as_read()
        return Response(NotificationSerializer(notification).data, status=status.HTTP_200_OK)

    @extend_schema(summary="Mark all notifications as read")
    @action(detail=False, methods=['post'], url_path='read-all')
    def mark_all_read(self, request):
        now = timezone.now()
        updated_count = Notification.objects.filter(
            recipient=request.user,
            is_read=False
        ).update(is_read=True, read_at=now)
        return Response({'updated_count': updated_count}, status=status.HTTP_200_OK)

    @extend_schema(summary="Count of unread notifications")
    @action(detail=False, methods=['get'], url_path='unread-count')
    def unread_count(self, request):
        count = Notification.objects.filter(recipient=request.user, is_read=False).count()
        return Response({'unread_count': count}, status=status.HTTP_200_OK)
