from datetime import date, timedelta
from django.core.management.base import BaseCommand
from django.db import transaction
from apps.tenants.models import Tenant
from apps.courses.models import (
    Programme,
    Course,
    Module,
    Lesson,
    CourseOffering,
    AcademicStatus,
    CourseLevel,
    DeliveryMode,
    CohortStatus,
    LessonType,
)


class Command(BaseCommand):
    help = 'Seeds initial academic programmes, courses, modules, lessons, and cohort offerings.'

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("Seeding academic courses and curricula..."))

        with transaction.atomic():
            # 1. Northstar Institute
            northstar = Tenant.objects.filter(slug='northstar').first()
            if northstar:
                self.seed_northstar(northstar)

            # 2. Apex Academy
            apex = Tenant.objects.filter(slug='apex').first()
            if apex:
                self.seed_apex(apex)

        self.stdout.write(self.style.SUCCESS("Academic programmes and courses seeded successfully."))

    def seed_northstar(self, tenant):
        # Programmes
        prog_exec, _ = Programme.objects.update_or_create(
            tenant=tenant,
            slug='executive-management',
            defaults={
                'name': 'Executive Management & Governance',
                'description': 'Senior executive development and institutional leadership.',
                'status': AcademicStatus.PUBLISHED,
            }
        )
        prog_fin, _ = Programme.objects.update_or_create(
            tenant=tenant,
            slug='financial-engineering',
            defaults={
                'name': 'Financial Engineering & Valuation',
                'description': 'Applied corporate valuation, financial modeling, and investment analysis.',
                'status': AcademicStatus.PUBLISHED,
            }
        )
        prog_tech, _ = Programme.objects.update_or_create(
            tenant=tenant,
            slug='technology-analytics',
            defaults={
                'name': 'Technology & Enterprise Analytics',
                'description': 'Applied machine learning, business intelligence, and cloud deployment.',
                'status': AcademicStatus.PUBLISHED,
            }
        )

        # Course 1: Strategic Leadership
        c1, _ = Course.objects.update_or_create(
            tenant=tenant,
            slug='executive-diploma-strategic-leadership',
            defaults={
                'programme': prog_exec,
                'title': 'Executive Diploma in Strategic Leadership',
                'short_description': 'Master organizational governance, enterprise risk mitigation, and transformative leadership paradigms.',
                'full_description': 'This comprehensive 12-week executive diploma is crafted for mid-to-senior level managers seeking to lead complex initiatives. Combining live case discussions with simulated boardroom decisions, the course equips participants with tactical framework skills.',
                'duration': '12 Weeks',
                'level': CourseLevel.ADVANCED,
                'status': AcademicStatus.PUBLISHED,
                'learning_objectives': [
                    'Formulate and execute high-yield enterprise strategic plans.',
                    'Lead cross-functional restructuring initiatives and corporate turnarounds.',
                    'Navigate regulatory compliance and institutional governance standards.',
                    'Communicate effectively with board directors, stakeholders, and investors.',
                ],
                'requirements': [
                    'Minimum 3 years managerial experience',
                    'Undergraduate degree or equivalent qualification',
                ],
            }
        )

        # Modules for Course 1
        m1, _ = Module.objects.update_or_create(
            tenant=tenant,
            course=c1,
            order=1,
            defaults={
                'title': 'Strategic Vision & Market Positioning',
                'description': 'Evaluating competitive advantages, industry forces, and disruptive business models.',
            }
        )
        Lesson.objects.update_or_create(
            tenant=tenant,
            module=m1,
            order=1,
            defaults={
                'title': 'Competitive Forces & Market Positioning Dynamics',
                'lesson_type': LessonType.ARTICLE,
                'content': 'Comprehensive breakdown of Porter five forces in the digital age.',
                'duration_minutes': 45,
                'is_preview': True,
            }
        )
        Lesson.objects.update_or_create(
            tenant=tenant,
            module=m1,
            order=2,
            defaults={
                'title': 'Disruptive Innovation Frameworks Lecture',
                'lesson_type': LessonType.VIDEO,
                'content': 'Recorded executive seminar by Prof. David Vance.',
                'duration_minutes': 60,
                'is_preview': False,
            }
        )

        m2, _ = Module.objects.update_or_create(
            tenant=tenant,
            course=c1,
            order=2,
            defaults={
                'title': 'Corporate Governance & Stakeholder Alignment',
                'description': 'Boardroom dynamics, fiduciary responsibilities, and ESG compliance architecture.',
            }
        )
        Lesson.objects.update_or_create(
            tenant=tenant,
            module=m2,
            order=1,
            defaults={
                'title': 'Fiduciary Accountability & Board Ethics',
                'lesson_type': LessonType.ARTICLE,
                'content': 'Case review of high-profile corporate governance collapses and preventive internal controls.',
                'duration_minutes': 50,
                'is_preview': False,
            }
        )

        # Cohorts for Course 1
        CourseOffering.objects.update_or_create(
            tenant=tenant,
            offering_code='NS-STRAT-2026-Q1',
            defaults={
                'course': c1,
                'cohort_name': 'Spring 2026 Executive Cohort',
                'start_date': date(2026, 3, 15),
                'end_date': date(2026, 6, 5),
                'application_deadline': date(2026, 3, 1),
                'capacity': 35,
                'price': 1450.00,
                'currency': 'USD',
                'delivery_mode': DeliveryMode.HYBRID,
                'status': CohortStatus.OPEN,
            }
        )

        # Course 2: FMVA
        c2, _ = Course.objects.update_or_create(
            tenant=tenant,
            slug='certified-financial-modeling-valuation',
            defaults={
                'programme': prog_fin,
                'title': 'Certified Financial Modeling & Valuation Analyst (FMVA)',
                'short_description': 'Hands-on mastery of dynamic DCF modeling, LBO evaluation, M&A analysis, and financial reporting.',
                'full_description': 'A comprehensive industry standard program designed for investment banking, private equity, and corporate finance practitioners.',
                'duration': '8 Weeks',
                'level': CourseLevel.INTERMEDIATE,
                'status': AcademicStatus.PUBLISHED,
                'learning_objectives': [
                    'Build three-statement dynamic forecasting models from scratch.',
                    'Conduct rigorous Discounted Cash Flow (DCF) and Comparable Company Analysis.',
                    'Model Leveraged Buyout (LBO) transactions and sensitivity tables.',
                ],
                'requirements': ['Basic accounting and spreadsheet proficiency'],
            }
        )

        CourseOffering.objects.update_or_create(
            tenant=tenant,
            offering_code='NS-FMVA-FLEX',
            defaults={
                'course': c2,
                'cohort_name': 'Rolling On-Demand Intake',
                'start_date': date(2026, 1, 1),
                'end_date': date(2026, 12, 31),
                'capacity': 150,
                'price': 850.00,
                'currency': 'USD',
                'delivery_mode': DeliveryMode.SELF_PACED,
                'status': CohortStatus.OPEN,
            }
        )

        self.stdout.write(self.style.SUCCESS(f"Seeded {tenant.name} curricula."))

    def seed_apex(self, tenant):
        prog_lead, _ = Programme.objects.update_or_create(
            tenant=tenant,
            slug='senior-leadership',
            defaults={
                'name': 'Senior Leadership & Board Direction',
                'description': 'Advanced executive programs for managing directors and C-suite officers.',
                'status': AcademicStatus.PUBLISHED,
            }
        )

        c1, _ = Course.objects.update_or_create(
            tenant=tenant,
            slug='high-performance-c-suite-leadership',
            defaults={
                'programme': prog_lead,
                'title': 'High-Performance C-Suite Leadership Programme',
                'short_description': 'An intensive retreat and hybrid programme for executive committee leaders driving enterprise transformation.',
                'full_description': 'Exclusive programme for CEOs, CFOs, and Managing Directors navigating technological transformation, international expansion, and shareholder relations.',
                'duration': '6 Weeks',
                'level': CourseLevel.ADVANCED,
                'status': AcademicStatus.PUBLISHED,
                'learning_objectives': [
                    'Hone personal executive presence and high-stakes negotiation skills.',
                    'Lead crisis communications during market shocks and operational disruptions.',
                ],
                'requirements': ['Currently serving at Director or C-Suite level'],
            }
        )

        CourseOffering.objects.update_or_create(
            tenant=tenant,
            offering_code='APEX-CSUITE-2026',
            defaults={
                'course': c1,
                'cohort_name': 'Summer Senior Leadership Cohort',
                'start_date': date(2026, 6, 1),
                'end_date': date(2026, 7, 15),
                'application_deadline': date(2026, 5, 10),
                'capacity': 20,
                'price': 2400.00,
                'currency': 'GBP',
                'delivery_mode': DeliveryMode.HYBRID,
                'status': CohortStatus.OPEN,
            }
        )

        self.stdout.write(self.style.SUCCESS(f"Seeded {tenant.name} curricula."))
