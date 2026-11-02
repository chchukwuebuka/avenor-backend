from django.core.management.base import BaseCommand
from django.utils import timezone
from apps.accounts.models import User
from apps.tenants.models import Tenant
from apps.courses.models import Course
from apps.communications.models import (
    DiscussionThread,
    DiscussionReply,
    ThreadUpvote,
    Announcement,
    Notification,
    DiscussionCategory,
    AnnouncementPriority,
    AnnouncementTarget,
    NotificationType,
)


class Command(BaseCommand):
    help = 'Seeds discussion threads, replies, upvotes, announcements, and scholar notifications.'

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE('Seeding communications, discussions, and bulletins...'))

        northstar = Tenant.objects.filter(slug='northstar').first()
        apex = Tenant.objects.filter(slug='apex').first()

        if not northstar:
            self.stdout.write(self.style.ERROR('Northstar tenant not found.'))
            return

        marcus = User.objects.filter(email='m.vance@northstar.avenor.edu').first()
        elena = User.objects.filter(email='elena.rostova@apex.avenor.edu').first()
        course = Course.objects.filter(tenant=northstar).first()

        if not marcus or not course:
            self.stdout.write(self.style.ERROR('User Marcus Vance or Course not found.'))
            return

        # 1. Discussion Thread 1 (Lecture Q&A)
        thread1, _ = DiscussionThread.objects.get_or_create(
            tenant=northstar,
            course=course,
            title='Best practices for PostgreSQL Row-Level Security performance at scale',
            defaults={
                'author': elena if elena else marcus,
                'category': DiscussionCategory.LECTURE_QA,
                'content': 'Are there measurable query planner overheads when enabling PostgreSQL RLS on tables exceeding 50 million records? What compound index patterns yield optimal partition pruning?',
                'upvotes_count': 14,
                'is_pinned': True,
            }
        )

        # Thread 1 Replies
        reply1, _ = DiscussionReply.objects.get_or_create(
            tenant=northstar,
            thread=thread1,
            author=marcus,
            defaults={
                'content': 'Make sure you create compound indexes with tenant_id as the leading column, and mark your RLS helper functions as LEAKPROOF so the optimizer pushes predicates down before expensive sequential scans.',
                'upvotes_count': 12,
                'is_faculty_endorsed': True,
            }
        )

        # 2. Discussion Thread 2 (Lab Help)
        thread2, _ = DiscussionThread.objects.get_or_create(
            tenant=northstar,
            course=course,
            title='Handling Raft leader election split-vote ties in lab 2.3 simulator',
            defaults={
                'author': marcus,
                'category': DiscussionCategory.ASSIGNMENT_HELP,
                'content': 'When simulating network latency partitions, randomize election timeouts between 150ms and 300ms to break symmetry across quorum candidates.',
                'upvotes_count': 8,
            }
        )

        # 3. Institutional Announcements
        Announcement.objects.get_or_create(
            tenant=northstar,
            title='Spring 2026 Academic Calendar & Laboratory Milestone Schedules',
            defaults={
                'author': marcus,
                'course': course,
                'priority': AnnouncementPriority.HIGH,
                'target': AnnouncementTarget.ALL_INSTITUTION,
                'content': 'All scholars are reminded that midterm laboratory assessments must be committed to your institutional Git repository branches by March 15, 2026 at 23:59 UTC.',
                'is_published': True,
                'published_at': timezone.now(),
            }
        )

        Announcement.objects.get_or_create(
            tenant=northstar,
            title='Faculty Masterclass: High-Throughput Distributed Ledger Architectures',
            defaults={
                'author': marcus,
                'course': course,
                'priority': AnnouncementPriority.NORMAL,
                'target': AnnouncementTarget.SPECIFIC_COURSE,
                'content': 'Join Prof. Alistair Thorne this Friday at 16:00 UTC for an interactive walkthrough of zero-copy network serialization with io_uring and Raft clusters.',
                'is_published': True,
                'published_at': timezone.now(),
            }
        )

        # 4. Scholar Notifications for Marcus
        Notification.objects.get_or_create(
            tenant=northstar,
            recipient=marcus,
            title='Laboratory Evaluation Conferred: Distinction',
            defaults={
                'notification_type': NotificationType.ASSIGNMENT_GRADED,
                'message': 'Your submission for Lab 2.3: Database Partitioning Engine has been evaluated: 98.00 / 100.',
                'action_url': '/grades',
                'is_read': False,
            }
        )

        Notification.objects.get_or_create(
            tenant=northstar,
            recipient=marcus,
            title='New Reply on Discussion Thread',
            defaults={
                'notification_type': NotificationType.DISCUSSION_REPLY,
                'message': "Elena Rostova replied to 'Handling Raft leader election split-vote ties...'",
                'action_url': f'/community?thread={thread2.id}',
                'is_read': True,
                'read_at': timezone.now(),
            }
        )

        self.stdout.write(self.style.SUCCESS('Successfully seeded discussion threads, announcements, and notifications.'))
