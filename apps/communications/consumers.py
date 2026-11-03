import uuid
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from channels.db import database_sync_to_async
from django.utils import timezone
from .models import DiscussionThread, DiscussionReply, ThreadUpvote, Notification, Announcement
from apps.tenants.models import Tenant


# -----------------------------------------------------------------------------
# Database Synchronization Helpers
# -----------------------------------------------------------------------------

@database_sync_to_async
def get_thread_data(thread_id: str):
    try:
        thread = DiscussionThread.objects.select_related('author', 'course', 'tenant').get(id=thread_id)
        return {
            'id': str(thread.id),
            'title': thread.title,
            'category': thread.category,
            'is_locked': thread.is_locked,
            'tenant_id': str(thread.tenant.id),
        }
    except DiscussionThread.DoesNotExist:
        return None


@database_sync_to_async
def create_discussion_reply(thread_id: str, user, content: str, parent_reply_id: str = None):
    try:
        thread = DiscussionThread.objects.select_related('tenant').get(id=thread_id)
        if thread.is_locked:
            return None, 'Thread is locked against further discourse.'

        parent = None
        if parent_reply_id:
            parent = DiscussionReply.objects.filter(id=parent_reply_id, thread=thread).first()

        is_faculty = getattr(user, 'role', '') in ('instructor', 'faculty', 'admin', 'dean')

        reply = DiscussionReply.objects.create(
            tenant=thread.tenant,
            thread=thread,
            author=user,
            parent_reply=parent,
            content=content,
            is_faculty_endorsed=is_faculty,
        )

        return {
            'id': str(reply.id),
            'thread_id': str(thread.id),
            'author_id': str(user.id),
            'author_name': user.get_full_name() or user.email,
            'author_email': user.email,
            'author_role': getattr(user, 'role', 'scholar'),
            'parent_reply_id': str(parent.id) if parent else None,
            'content': reply.content,
            'upvotes_count': reply.upvotes_count,
            'is_faculty_endorsed': reply.is_faculty_endorsed,
            'created_at': reply.created_at.isoformat(),
        }, None
    except Exception as e:
        return None, str(e)


@database_sync_to_async
def toggle_thread_upvote_record(thread_id: str, user):
    try:
        thread = DiscussionThread.objects.get(id=thread_id)
        upvote = ThreadUpvote.objects.filter(thread=thread, user=user).first()
        if upvote:
            upvote.delete()
            if thread.upvotes_count > 0:
                thread.upvotes_count -= 1
                thread.save(update_fields=['upvotes_count'])
            has_upvoted = False
        else:
            ThreadUpvote.objects.create(thread=thread, user=user)
            thread.upvotes_count += 1
            thread.save(update_fields=['upvotes_count'])
            has_upvoted = True

        return thread.upvotes_count, has_upvoted
    except Exception:
        return 0, False


@database_sync_to_async
def mark_reply_endorsement(reply_id: str, endorsed: bool):
    try:
        reply = DiscussionReply.objects.get(id=reply_id)
        reply.is_faculty_endorsed = endorsed
        reply.save(update_fields=['is_faculty_endorsed'])
        return True
    except DiscussionReply.DoesNotExist:
        return False


# -----------------------------------------------------------------------------
# 1. Discussion Consumer
# -----------------------------------------------------------------------------

class DiscussionConsumer(AsyncJsonWebsocketConsumer):
    """
    Real-time peer and faculty discourse consumer.
    Provides instant replies, typing presence, upvoting, and endorsement broadcasts.
    """
    async def connect(self):
        self.thread_id = self.scope['url_route']['kwargs'].get('thread_id')
        self.room_group_name = f"thread_{self.thread_id}"

        # Verify thread exists in database
        self.thread_info = await get_thread_data(self.thread_id)
        if not self.thread_info:
            await self.close(code=4004)
            return

        # Join thread room group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        await self.accept()

        user = self.scope.get('user')
        user_name = user.get_full_name() or user.email if user and user.is_authenticated else 'Anonymous Scholar'

        await self.send_json({
            'type': 'connection_established',
            'thread_id': self.thread_id,
            'title': self.thread_info['title'],
            'is_locked': self.thread_info['is_locked'],
            'current_user': user_name,
            'timestamp': timezone.now().isoformat(),
        })

    async def disconnect(self, close_code):
        if hasattr(self, 'room_group_name'):
            await self.channel_layer.group_discard(
                self.room_group_name,
                self.channel_name
            )

    async def receive_json(self, content):
        action = content.get('action')
        user = self.scope.get('user')

        if not user or not user.is_authenticated:
            await self.send_json({
                'type': 'error',
                'message': 'Authentication credentials required for interactive contributions.'
            })
            return

        if action == 'reply':
            text = content.get('content', '').strip()
            parent_id = content.get('parent_reply_id')

            if not text:
                await self.send_json({'type': 'error', 'message': 'Reply content cannot be empty.'})
                return

            reply_data, err = await create_discussion_reply(self.thread_id, user, text, parent_id)
            if err:
                await self.send_json({'type': 'error', 'message': err})
                return

            # Broadcast new reply to all subscribers in thread room
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'broadcast_reply',
                    'reply': reply_data,
                }
            )

        elif action in ('typing_start', 'typing_stop'):
            is_typing = (action == 'typing_start')
            user_label = user.get_full_name() or user.email
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'broadcast_typing',
                    'user_id': str(user.id),
                    'user_name': user_label,
                    'is_typing': is_typing,
                }
            )

        elif action == 'upvote':
            upvotes_count, has_upvoted = await toggle_thread_upvote_record(self.thread_id, user)
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'broadcast_upvote',
                    'thread_id': self.thread_id,
                    'upvotes_count': upvotes_count,
                    'actor_id': str(user.id),
                }
            )

        elif action == 'endorse':
            reply_id = content.get('reply_id')
            endorsed = content.get('endorsed', True)
            user_role = getattr(user, 'role', '')

            if user_role not in ('instructor', 'faculty', 'admin', 'dean'):
                await self.send_json({'type': 'error', 'message': 'Only faculty may endorse replies.'})
                return

            ok = await mark_reply_endorsement(reply_id, endorsed)
            if ok:
                await self.channel_layer.group_send(
                    self.room_group_name,
                    {
                        'type': 'broadcast_endorsement',
                        'reply_id': reply_id,
                        'is_endorsed': endorsed,
                        'endorsed_by': user.get_full_name() or user.email,
                    }
                )

    # -------------------------------------------------------------------------
    # Group Event Handlers
    # -------------------------------------------------------------------------

    async def broadcast_reply(self, event):
        await self.send_json({
            'type': 'reply_created',
            'reply': event['reply'],
        })

    async def broadcast_typing(self, event):
        await self.send_json({
            'type': 'typing_presence',
            'user_id': event['user_id'],
            'user_name': event['user_name'],
            'is_typing': event['is_typing'],
        })

    async def broadcast_upvote(self, event):
        await self.send_json({
            'type': 'upvote_updated',
            'thread_id': event['thread_id'],
            'upvotes_count': event['upvotes_count'],
            'actor_id': event['actor_id'],
        })

    async def broadcast_endorsement(self, event):
        await self.send_json({
            'type': 'endorsement_updated',
            'reply_id': event['reply_id'],
            'is_endorsed': event['is_endorsed'],
            'endorsed_by': event['endorsed_by'],
        })


# -----------------------------------------------------------------------------
# 2. Notification Consumer
# -----------------------------------------------------------------------------

class NotificationConsumer(AsyncJsonWebsocketConsumer):
    """
    Personalized real-time notification dispatch consumer.
    Streams grade notifications, faculty answers, and credential conferrals.
    """
    async def connect(self):
        user = self.scope.get('user')
        if not user or not user.is_authenticated:
            await self.close(code=4001)
            return

        self.user_group_name = f"user_notifications_{user.id}"

        await self.channel_layer.group_add(
            self.user_group_name,
            self.channel_name
        )
        await self.accept()

        await self.send_json({
            'type': 'connection_established',
            'channel': 'notifications',
            'user_id': str(user.id),
            'status': 'connected',
        })

    async def disconnect(self, close_code):
        if hasattr(self, 'user_group_name'):
            await self.channel_layer.group_discard(
                self.user_group_name,
                self.channel_name
            )

    async def receive_json(self, content):
        action = content.get('action')
        user = self.scope.get('user')

        if action == 'mark_read':
            notification_id = content.get('notification_id')
            await self.mark_notification_read(notification_id, user)
            await self.send_json({
                'type': 'notification_read_ack',
                'notification_id': notification_id,
            })

    @database_sync_to_async
    def mark_notification_read(self, notif_id: str, user):
        Notification.objects.filter(id=notif_id, recipient=user).update(
            is_read=True,
            read_at=timezone.now()
        )

    async def notification_alert(self, event):
        await self.send_json({
            'type': 'notification_received',
            'notification': event['notification'],
        })


# -----------------------------------------------------------------------------
# 3. Announcement Consumer
# -----------------------------------------------------------------------------

class AnnouncementConsumer(AsyncJsonWebsocketConsumer):
    """
    Tenant-wide institutional bulletin broadcast consumer.
    """
    async def connect(self):
        self.tenant_slug = self.scope['url_route']['kwargs'].get('tenant_slug')
        self.announcement_group = f"announcements_{self.tenant_slug}"

        await self.channel_layer.group_add(
            self.announcement_group,
            self.channel_name
        )
        await self.accept()

        await self.send_json({
            'type': 'connection_established',
            'tenant_slug': self.tenant_slug,
            'channel': 'announcements',
        })

    async def disconnect(self, close_code):
        if hasattr(self, 'announcement_group'):
            await self.channel_layer.group_discard(
                self.announcement_group,
                self.channel_name
            )

    async def announcement_broadcast(self, event):
        await self.send_json({
            'type': 'announcement_received',
            'announcement': event['announcement'],
        })
