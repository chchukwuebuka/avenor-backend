from decimal import Decimal
from django.core.management.base import BaseCommand
from django.utils import timezone
from apps.tenants.models import Tenant
from apps.finance.models import (
    SubscriptionPlan,
    TenantSubscription,
    Invoice,
    Transaction,
    SubscriptionTier,
    SubscriptionStatus,
    BillingCycle,
    InvoiceStatus,
    PaymentGateway,
    TransactionStatus,
)


class Command(BaseCommand):
    help = 'Seeds platform subscription plans and demo institutional financial records.'

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("Seeding subscription plans and finance records..."))

        # 1. Platform Subscription Plans
        plans_data = [
            {
                'name': 'Starter Academy',
                'slug': 'starter-academy',
                'tier': SubscriptionTier.STARTER,
                'description': 'Designed for specialized boutique training institutes and vocational academies.',
                'price_monthly': Decimal('499.00'),
                'price_annual': Decimal('4990.00'),
                'currency': 'USD',
                'max_active_scholars': 500,
                'max_faculty_seats': 20,
                'max_storage_gb': 50,
                'features': {
                    'white_label': True,
                    'custom_domain': True,
                    'api_access': False,
                    'sso': False,
                    'priority_support': False,
                    'analytics_depth': 'standard',
                },
                'is_active': True,
                'is_public': True,
            },
            {
                'name': 'Professional Institute',
                'slug': 'professional-institute',
                'tier': SubscriptionTier.PROFESSIONAL,
                'description': 'Engineered for scaling colleges and professional certification bodies requiring high capacity.',
                'price_monthly': Decimal('1499.00'),
                'price_annual': Decimal('14990.00'),
                'currency': 'USD',
                'max_active_scholars': 2500,
                'max_faculty_seats': 100,
                'max_storage_gb': 250,
                'features': {
                    'white_label': True,
                    'custom_domain': True,
                    'api_access': True,
                    'sso': False,
                    'priority_support': True,
                    'analytics_depth': 'advanced',
                },
                'is_active': True,
                'is_public': True,
            },
            {
                'name': 'Enterprise University',
                'slug': 'enterprise-university',
                'tier': SubscriptionTier.ENTERPRISE,
                'description': 'Flagship tier for multi-campus universities and global executive training institutions.',
                'price_monthly': Decimal('4999.00'),
                'price_annual': Decimal('49990.00'),
                'currency': 'USD',
                'max_active_scholars': 15000,
                'max_faculty_seats': 500,
                'max_storage_gb': 1000,
                'features': {
                    'white_label': True,
                    'custom_domain': True,
                    'api_access': True,
                    'sso': True,
                    'priority_support': True,
                    'analytics_depth': 'enterprise',
                    'dedicated_cluster': True,
                    'sla_guarantee': '99.95%',
                },
                'is_active': True,
                'is_public': True,
            },
            {
                'name': 'Custom Consortium',
                'slug': 'custom-consortium',
                'tier': SubscriptionTier.CUSTOM,
                'description': 'Tailored infrastructure agreements for state university networks and enterprise groups.',
                'price_monthly': Decimal('9999.00'),
                'price_annual': Decimal('99990.00'),
                'currency': 'USD',
                'max_active_scholars': None,
                'max_faculty_seats': None,
                'max_storage_gb': 5000,
                'features': {
                    'white_label': True,
                    'custom_domain': True,
                    'api_access': True,
                    'sso': True,
                    'priority_support': True,
                    'multi_region_failover': True,
                    'dedicated_account_manager': True,
                },
                'is_active': True,
                'is_public': False,
            },
        ]

        plans = {}
        for pdata in plans_data:
            plan, created = SubscriptionPlan.objects.update_or_create(
                slug=pdata['slug'],
                defaults=pdata
            )
            plans[pdata['slug']] = plan
            action = "Created" if created else "Updated"
            self.stdout.write(f"  {action} plan: {plan.name}")

        now = timezone.now()

        # 2. Apex Executive Academy Subscriptions & Invoicing
        apex_tenant = Tenant.objects.filter(slug='apex').first()
        if apex_tenant:
            ent_plan = plans['enterprise-university']
            apex_sub, _ = TenantSubscription.objects.update_or_create(
                tenant=apex_tenant,
                defaults={
                    'plan': ent_plan,
                    'billing_cycle': BillingCycle.ANNUAL,
                    'status': SubscriptionStatus.ACTIVE,
                    'current_period_start': now - timezone.timedelta(days=90),
                    'current_period_end': now + timezone.timedelta(days=275),
                    'cancel_at_period_end': False,
                    'gateway_customer_id': 'cus_apex_corp_99',
                    'gateway_subscription_id': 'sub_apex_ent_2026',
                }
            )

            inv_apex, _ = Invoice.objects.update_or_create(
                invoice_number='INV-2026-APEX-001',
                defaults={
                    'tenant': apex_tenant,
                    'subscription': apex_sub,
                    'amount_due': ent_plan.price_annual,
                    'amount_paid': ent_plan.price_annual,
                    'currency': 'USD',
                    'status': InvoiceStatus.PAID,
                    'due_date': (now - timezone.timedelta(days=76)).date(),
                    'paid_at': now - timezone.timedelta(days=90),
                    'line_items': [{
                        'description': 'Enterprise University Tier Annual License (15,000 Scholar Allocation)',
                        'quantity': 1,
                        'unit_price': str(ent_plan.price_annual),
                        'total': str(ent_plan.price_annual),
                    }],
                    'notes': 'Settled via Corporate Wire Transfer reconciliation.'
                }
            )

            Transaction.objects.update_or_create(
                reference='TXN-20260115-APEX-ENTERPRISE',
                defaults={
                    'tenant': apex_tenant,
                    'invoice': inv_apex,
                    'gateway': PaymentGateway.WIRE_TRANSFER,
                    'gateway_reference': 'WIRE-CHASE-99214A',
                    'amount': ent_plan.price_annual,
                    'currency': 'USD',
                    'status': TransactionStatus.SUCCEEDED,
                    'payment_method_type': 'bank_transfer',
                    'metadata': {'bank': 'JPMorgan Chase', 'verified_by': 'Finance Controller'}
                }
            )
            self.stdout.write("  Configured Apex Executive Academy finance & subscription.")

        # 3. Northstar Technical Institute Subscriptions & Invoicing
        northstar_tenant = Tenant.objects.filter(slug='northstar').first()
        if northstar_tenant:
            pro_plan = plans['professional-institute']
            ns_sub, _ = TenantSubscription.objects.update_or_create(
                tenant=northstar_tenant,
                defaults={
                    'plan': pro_plan,
                    'billing_cycle': BillingCycle.ANNUAL,
                    'status': SubscriptionStatus.ACTIVE,
                    'current_period_start': now - timezone.timedelta(days=45),
                    'current_period_end': now + timezone.timedelta(days=320),
                    'cancel_at_period_end': False,
                    'gateway_customer_id': 'cus_northstar_poly_42',
                    'gateway_subscription_id': 'sub_northstar_pro_2026',
                }
            )

            inv_ns, _ = Invoice.objects.update_or_create(
                invoice_number='INV-2026-NORTHSTAR-001',
                defaults={
                    'tenant': northstar_tenant,
                    'subscription': ns_sub,
                    'amount_due': pro_plan.price_annual,
                    'amount_paid': pro_plan.price_annual,
                    'currency': 'USD',
                    'status': InvoiceStatus.PAID,
                    'due_date': (now - timezone.timedelta(days=31)).date(),
                    'paid_at': now - timezone.timedelta(days=45),
                    'line_items': [{
                        'description': 'Professional Institute Tier Annual License (2,500 Scholar Allocation)',
                        'quantity': 1,
                        'unit_price': str(pro_plan.price_annual),
                        'total': str(pro_plan.price_annual),
                    }],
                    'notes': 'Settled via institutional Stripe payment.'
                }
            )

            Transaction.objects.update_or_create(
                reference='TXN-20260201-NORTHSTAR-PRO',
                defaults={
                    'tenant': northstar_tenant,
                    'invoice': inv_ns,
                    'gateway': PaymentGateway.STRIPE,
                    'gateway_reference': 'ch_3N82bH4E89vN',
                    'amount': pro_plan.price_annual,
                    'currency': 'USD',
                    'status': TransactionStatus.SUCCEEDED,
                    'payment_method_type': 'card',
                    'metadata': {'brand': 'Visa', 'last4': '4242', 'exp_month': 12, 'exp_year': 2028}
                }
            )
            self.stdout.write("  Configured Northstar Technical Institute finance & subscription.")

        self.stdout.write(self.style.SUCCESS("Successfully seeded finance data!"))
