import uuid
from django.test import TransactionTestCase
from channels.testing import WebsocketCommunicator
from channels.db import database_sync_to_async
from rest_framework_simplejwt.tokens import AccessToken

from config.asgi import application
from apps.accounts.models import User
from apps.tenants.models import Tenant
from apps.courses.models import Programme, Course, Module, Lesson, AcademicStatus
from apps.communications.models import DiscussionThread, DiscussionReply, ThreadUpvote, Notification


class WebSocketIntegrationTests(TransactionTestCase):
    def setUp(self):
        # Tenant
        self.tenant = Tenant.objects.create(
            name="Apex Executive Academy",
            slug="apex-ws-test",
            contact_email="colloquium@apex.test"
        )

        # Users
        self.student = User.objects.create_user(
            email="scholar.ws@apex.test",
            password="Password123!",
            first_name="Elena",
            last_name="Rostova"
        )
        self.faculty = User.objects.create_user(
            email="dean.ws@apex.test",
            password="Password123!",
            first_name="Prof",
            last_name="Hawthorne",
            is_staff=True
        )

        # Academic Course
        self.prog = Programme.objects.create(
            tenant=self.tenant,
            name="Executive MBA",
            slug="emba-ws"
        )
        self.course = Course.objects.create(
            tenant=self.tenant,
            programme=self.prog,
            title="Valuation in Hostile Takeovers",
            slug="corp-880-ws",
            status=AcademicStatus.PUBLISHED,
        )
        self.module = Module.objects.create(
            tenant=self.tenant,
            course=self.course,
            title="Module 1: Discounted Cash Flow",
            order=1
        )
        self.lesson = Lesson.objects.create(
            tenant=self.tenant,
            module=self.module,
            title="Lesson 1.1: WACC Calculations",
            order=1
        )

        # Discussion Thread
        self.thread = DiscussionThread.objects.create(
            tenant=self.tenant,
            course=self.course,
            lesson=self.lesson,
            author=self.student,
            title="Optimal Terminal Value Assumptions in Distressed M&A",
            content="What discount rate should be applied to distressed asset recovery?"
        )

    async def test_discussion_consumer_connect_and_welcome(self):
        communicator = WebsocketCommunicator(
            application,
            f"/ws/communications/threads/{self.thread.id}/"
        )
        connected, _ = await communicator.connect()
        self.assertTrue(connected)

        response = await communicator.receive_json_from()
        self.assertEqual(response['type'], 'connection_established')
        self.assertEqual(response['thread_id'], str(self.thread.id))
        self.assertEqual(response['title'], self.thread.title)

        await communicator.disconnect()

    async def test_discussion_consumer_reply_broadcast(self):
        token = str(AccessToken.for_user(self.student))
        communicator = WebsocketCommunicator(
            application,
            f"/ws/communications/threads/{self.thread.id}/?token={token}"
        )
        connected, _ = await communicator.connect()
        self.assertTrue(connected)

        # Drain welcome message
        await communicator.receive_json_from()

        # Submit peer reply via WebSocket
        await communicator.send_json_to({
            'action': 'reply',
            'content': 'We recommend using an adjusted APV (Adjusted Present Value) framework.',
        })

        broadcast = await communicator.receive_json_from()
        self.assertEqual(broadcast['type'], 'reply_created')
        self.assertIn('reply', broadcast)
        self.assertEqual(
            broadcast['reply']['content'],
            'We recommend using an adjusted APV (Adjusted Present Value) framework.'
        )
        self.assertEqual(broadcast['reply']['author_email'], self.student.email)

        # Verify persisted in database
        reply_count = await database_sync_to_async(
            lambda: DiscussionReply.objects.filter(thread=self.thread).count()
        )()
        self.assertEqual(reply_count, 1)

        await communicator.disconnect()

    async def test_discussion_consumer_typing_presence(self):
        token = str(AccessToken.for_user(self.student))
        communicator = WebsocketCommunicator(
            application,
            f"/ws/communications/threads/{self.thread.id}/?token={token}"
        )
        connected, _ = await communicator.connect()
        self.assertTrue(connected)

        # Drain welcome message
        await communicator.receive_json_from()

        # Send typing_start
        await communicator.send_json_to({'action': 'typing_start'})
        typing_event = await communicator.receive_json_from()
        self.assertEqual(typing_event['type'], 'typing_presence')
        self.assertTrue(typing_event['is_typing'])

        # Send typing_stop
        await communicator.send_json_to({'action': 'typing_stop'})
        stop_event = await communicator.receive_json_from()
        self.assertEqual(stop_event['type'], 'typing_presence')
        self.assertFalse(stop_event['is_typing'])

        await communicator.disconnect()

    async def test_discussion_consumer_upvote_toggle(self):
        token = str(AccessToken.for_user(self.student))
        communicator = WebsocketCommunicator(
            application,
            f"/ws/communications/threads/{self.thread.id}/?token={token}"
        )
        connected, _ = await communicator.connect()
        self.assertTrue(connected)

        # Drain welcome message
        await communicator.receive_json_from()

        # Upvote 1st time -> 1
        await communicator.send_json_to({'action': 'upvote'})
        upvote_res = await communicator.receive_json_from()
        self.assertEqual(upvote_res['type'], 'upvote_updated')
        self.assertEqual(upvote_res['upvotes_count'], 1)

        # Upvote 2nd time -> toggle off to 0
        await communicator.send_json_to({'action': 'upvote'})
        upvote_res2 = await communicator.receive_json_from()
        self.assertEqual(upvote_res2['type'], 'upvote_updated')
        self.assertEqual(upvote_res2['upvotes_count'], 0)

        await communicator.disconnect()

    async def test_discussion_consumer_nonexistent_thread_closes(self):
        fake_uuid = uuid.uuid4()
        communicator = WebsocketCommunicator(
            application,
            f"/ws/communications/threads/{fake_uuid}/"
        )
        connected, code = await communicator.connect()
        self.assertFalse(connected)
        self.assertEqual(code, 4004)

    async def test_notification_consumer_authenticated(self):
        token = str(AccessToken.for_user(self.student))
        communicator = WebsocketCommunicator(
            application,
            f"/ws/communications/notifications/?token={token}"
        )
        connected, _ = await communicator.connect()
        self.assertTrue(connected)

        welcome = await communicator.receive_json_from()
        self.assertEqual(welcome['type'], 'connection_established')
        self.assertEqual(welcome['channel'], 'notifications')
        self.assertEqual(welcome['user_id'], str(self.student.id))

        await communicator.disconnect()

    async def test_notification_consumer_unauthenticated_rejects(self):
        communicator = WebsocketCommunicator(
            application,
            "/ws/communications/notifications/"
        )
        connected, code = await communicator.connect()
        self.assertFalse(connected)
        self.assertEqual(code, 4001)

    async def test_announcement_consumer_connect(self):
        communicator = WebsocketCommunicator(
            application,
            f"/ws/communications/announcements/{self.tenant.slug}/"
        )
        connected, _ = await communicator.connect()
        self.assertTrue(connected)

        welcome = await communicator.receive_json_from()
        self.assertEqual(welcome['type'], 'connection_established')
        self.assertEqual(welcome['tenant_slug'], self.tenant.slug)

        await communicator.disconnect()
