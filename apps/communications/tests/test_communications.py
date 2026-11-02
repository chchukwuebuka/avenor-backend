from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework import status
from apps.accounts.models import User
from apps.tenants.models import Tenant
from apps.courses.models import Programme, Course, Module, Lesson, AcademicStatus
from apps.communications.models import (
    DiscussionThread,
    DiscussionReply,
    ThreadUpvote,
    Announcement,
    Notification,
    DiscussionCategory,
    AnnouncementPriority,
    NotificationType,
)


class CommunicationsModelAndAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()

        # Tenant
        self.tenant = Tenant.objects.create(
            name="Apex Executive Academy",
            slug="apex-comm-test",
            contact_email="colloquium@apex.test"
        )

        # Scholar
        self.student = User.objects.create_user(
            email="scholar@apex.test",
            password="Password123!",
            first_name="Elena",
            last_name="Rostova"
        )

        # Faculty Member
        self.faculty = User.objects.create_user(
            email="dean@apex.test",
            password="Password123!",
            first_name="Prof",
            last_name="Hawthorne",
            is_staff=True
        )

        # Course
        self.prog = Programme.objects.create(
            tenant=self.tenant,
            name="Executive Leadership",
            slug="exec-lead"
        )
        self.course = Course.objects.create(
            tenant=self.tenant,
            programme=self.prog,
            title="Strategic Negotiation",
            slug="strategic-negotiation",
            short_description="Executive conflict resolution",
            status=AcademicStatus.PUBLISHED
        )

    def test_discussion_thread_creation_and_listing(self):
        self.client.force_authenticate(user=self.student)
        url = "/api/v1/communications/threads/"

        # Create thread
        resp = self.client.post(url, {
            'course_id': str(self.course.id),
            'category': DiscussionCategory.LECTURE_QA,
            'title': 'BATNA calculation under imperfect information',
            'content': 'How do you price non-monetary concession options?'
        }, format='json')

        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        thread_id = resp.data['id']

        # List threads
        list_resp = self.client.get(f"/api/v1/communications/threads/?course_id={self.course.id}")
        self.assertEqual(list_resp.status_code, status.HTTP_200_OK)
        results = list_resp.data.get('results', list_resp.data) if isinstance(list_resp.data, dict) else list_resp.data
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['title'], 'BATNA calculation under imperfect information')

    def test_reply_creation_and_notification_dispatch(self):
        thread = DiscussionThread.objects.create(
            tenant=self.tenant,
            course=self.course,
            author=self.student,
            category=DiscussionCategory.LECTURE_QA,
            title='Game theory in multivariable contracts',
            content='Does Nash equilibrium apply to multi-round dispute resolutions?'
        )

        # Faculty replies to student's thread
        self.client.force_authenticate(user=self.faculty)
        reply_url = f"/api/v1/communications/threads/{thread.id}/reply/"

        resp = self.client.post(reply_url, {
            'content': 'Yes, provided payoffs are modeled as repeated games with discount factors.'
        }, format='json')

        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertTrue(resp.data['is_faculty_endorsed'])

        # Check that student received an automated notification
        notif = Notification.objects.filter(recipient=self.student).first()
        self.assertIsNotNone(notif)
        self.assertEqual(notif.notification_type, 'discussion_reply')
        self.assertFalse(notif.is_read)

    def test_upvote_toggle_action(self):
        thread = DiscussionThread.objects.create(
            tenant=self.tenant,
            course=self.course,
            author=self.student,
            title='Valuation models in distressed mergers',
            content='Discounted cash flow sensitivity parameters'
        )

        self.client.force_authenticate(user=self.faculty)
        upvote_url = f"/api/v1/communications/threads/{thread.id}/upvote/"

        # 1. Upvote ON
        resp1 = self.client.post(upvote_url)
        self.assertEqual(resp1.status_code, status.HTTP_200_OK)
        self.assertEqual(resp1.data['upvotes_count'], 1)
        self.assertTrue(resp1.data['has_upvoted'])

        # 2. Upvote OFF (toggle)
        resp2 = self.client.post(upvote_url)
        self.assertEqual(resp2.status_code, status.HTTP_200_OK)
        self.assertEqual(resp2.data['upvotes_count'], 0)
        self.assertFalse(resp2.data['has_upvoted'])

    def test_announcements_publishing_and_permissions(self):
        ann_url = "/api/v1/communications/announcements/"

        # Student cannot author announcements (403 Forbidden)
        self.client.force_authenticate(user=self.student)
        resp_denied = self.client.post(ann_url, {
            'title': 'Student Post',
            'content': 'Unauthorized bulletin'
        }, format='json')
        self.assertEqual(resp_denied.status_code, status.HTTP_403_FORBIDDEN)

        # Faculty creates announcement (201 Created)
        self.client.force_authenticate(user=self.faculty)
        resp_created = self.client.post(ann_url, {
            'title': 'Midterm Negotiation Simulation Schedule',
            'content': 'Simulations commence on Friday at 09:00 UTC.',
            'priority': AnnouncementPriority.HIGH
        }, format='json')
        self.assertEqual(resp_created.status_code, status.HTTP_201_CREATED)

        # Scholar can view published announcements
        self.client.force_authenticate(user=self.student)
        resp_list = self.client.get(ann_url)
        self.assertEqual(resp_list.status_code, status.HTTP_200_OK)
        results = resp_list.data.get('results', resp_list.data) if isinstance(resp_list.data, dict) else resp_list.data
        self.assertEqual(len(results), 1)

    def test_notifications_read_flow(self):
        notif = Notification.objects.create(
            tenant=self.tenant,
            recipient=self.student,
            notification_type=NotificationType.ASSIGNMENT_GRADED,
            title='Grading Published',
            message='Your negotiation brief received 94/100.'
        )

        self.client.force_authenticate(user=self.student)

        # Check unread count
        resp_count = self.client.get("/api/v1/communications/notifications/unread-count/")
        self.assertEqual(resp_count.data['unread_count'], 1)

        # Mark as read
        resp_read = self.client.post(f"/api/v1/communications/notifications/{notif.id}/read/")
        self.assertEqual(resp_read.status_code, status.HTTP_200_OK)
        self.assertTrue(resp_read.data['is_read'])

        # Check unread count again
        resp_count_after = self.client.get("/api/v1/communications/notifications/unread-count/")
        self.assertEqual(resp_count_after.data['unread_count'], 0)
