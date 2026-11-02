from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import DiscussionThreadViewSet, AnnouncementViewSet, NotificationViewSet

router = DefaultRouter()
router.register('threads', DiscussionThreadViewSet, basename='discussion-thread')
router.register('announcements', AnnouncementViewSet, basename='announcement')
router.register('notifications', NotificationViewSet, basename='notification')

urlpatterns = [
    path('', include(router.urls)),
]
