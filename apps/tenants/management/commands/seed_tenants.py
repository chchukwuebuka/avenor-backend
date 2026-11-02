from django.core.management.base import BaseCommand
from django.utils import timezone
from apps.tenants.models import Tenant, TenantDomain, TenantBranding, TenantSettings, InstitutionType, TenantStatus

class Command(BaseCommand):
    help = 'Seeds initial demonstration tenants (Northstar Institute & Apex Academy)'

    def handle(self, *args, **options):
        self.stdout.write('Seeding demonstration tenants...')

        # 1. Northstar Institute of Professional Studies (Demo Tenant)
        northstar, created = Tenant.objects.get_or_create(
            slug='northstar',
            defaults={
                'name': 'Northstar Institute of Professional Studies',
                'institution_type': InstitutionType.PROFESSIONAL_TRAINING,
                'description': 'A premier institution offering accredited executive diplomas and technology certifications.',
                'status': TenantStatus.ACTIVE,
                'timezone': 'UTC',
                'default_currency': 'USD',
                'contact_email': 'admissions@northstar.edu',
                'contact_phone': '+1 (555) 234-5678',
            }
        )

        # Primary Domains
        TenantDomain.objects.get_or_create(
            tenant=northstar,
            hostname='northstar.avenor.local',
            defaults={
                'is_primary': True,
                'is_verified': True,
                'verified_at': timezone.now(),
            }
        )
        TenantDomain.objects.get_or_create(
            tenant=northstar,
            hostname='northstar.localhost',
            defaults={
                'is_primary': False,
                'is_verified': True,
                'verified_at': timezone.now(),
            }
        )

        # Branding
        TenantBranding.objects.update_or_create(
            tenant=northstar,
            defaults={
                'site_name': 'Northstar Institute',
                'primary_colour': '#111111',
                'secondary_colour': '#F5F5F5',
                'accent_colour': '#1E3A8A', # Restrained Navy
                'background_colour': '#FFFFFF',
                'text_colour': '#111111',
                'heading_font': 'Sora',
                'body_font': 'Manrope',
                'support_email': 'support@northstar.edu',
                'support_phone': '+1 (555) 234-5678',
                'footer_text': '© 2026 Northstar Institute of Professional Studies. Powered by Avenor.',
            }
        )

        # Settings
        TenantSettings.objects.get_or_create(
            tenant=northstar,
            defaults={
                'public_registration_enabled': True,
                'applications_enabled': True,
                'learner_registration_enabled': True,
                'certificates_enabled': True,
                'payment_enabled': True,
                'public_course_catalogue_enabled': True,
            }
        )
        self.stdout.write(self.style.SUCCESS(f"Tenant 'Northstar Institute' initialized (slug: {northstar.slug})"))

        # 2. Apex Academy (Secondary Tenant for Multi-Tenant Isolation Testing)
        apex, created = Tenant.objects.get_or_create(
            slug='apex',
            defaults={
                'name': 'Apex Executive Academy',
                'institution_type': InstitutionType.CORPORATE_LEARNING,
                'description': 'Corporate leadership development and international management training.',
                'status': TenantStatus.ACTIVE,
                'timezone': 'UTC',
                'default_currency': 'USD',
                'contact_email': 'contact@apexacademy.org',
                'contact_phone': '+44 20 7946 0912',
            }
        )

        # Primary Domains
        TenantDomain.objects.get_or_create(
            tenant=apex,
            hostname='apex.avenor.local',
            defaults={
                'is_primary': True,
                'is_verified': True,
                'verified_at': timezone.now(),
            }
        )
        TenantDomain.objects.get_or_create(
            tenant=apex,
            hostname='apex.localhost',
            defaults={
                'is_primary': False,
                'is_verified': True,
                'verified_at': timezone.now(),
            }
        )

        # Branding
        TenantBranding.objects.update_or_create(
            tenant=apex,
            defaults={
                'site_name': 'Apex Executive Academy',
                'primary_colour': '#111111',
                'secondary_colour': '#F5F5F5',
                'accent_colour': '#0D9488', # Restrained Teal
                'background_colour': '#FFFFFF',
                'text_colour': '#111111',
                'heading_font': 'Sora',
                'body_font': 'Manrope',
                'support_email': 'support@apexacademy.org',
                'support_phone': '+44 20 7946 0912',
                'footer_text': '© 2026 Apex Executive Academy. Enterprise Learning on Avenor.',
            }
        )

        # Settings
        TenantSettings.objects.get_or_create(
            tenant=apex,
            defaults={
                'public_registration_enabled': True,
                'applications_enabled': True,
                'learner_registration_enabled': True,
                'certificates_enabled': True,
                'payment_enabled': True,
                'public_course_catalogue_enabled': True,
            }
        )
        self.stdout.write(self.style.SUCCESS(f"Tenant 'Apex Executive Academy' initialized (slug: {apex.slug})"))
