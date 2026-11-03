from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    re_path(
        r'^ws/communications/threads/(?P<thread_id>[0-9a-f-]+)/?$',
        consumers.DiscussionConsumer.as_asgi()
    ),
    re_path(
        r'^ws/communications/notifications/?$',
        consumers.NotificationConsumer.as_asgi()
    ),
    re_path(
        r'^ws/communications/announcements/(?P<tenant_slug>[\w-]+)/?$',
        consumers.AnnouncementConsumer.as_asgi()
    ),
]
