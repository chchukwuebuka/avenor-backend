from decimal import Decimal
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework import status

from apps.accounts.models import User
from apps.tenants.models import Tenant
from apps.memberships.models import TenantMembership, Role, MembershipRole, MembershipStatus
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


class FinanceEngineTests(TestCase):
    def setUp(self):
        self.client = APIClient()

        # Tenant
        self.tenant = Tenant.objects.create(
            name="Horizon Business College",
            slug="horizon-college",
            contact_email="finance@horizon.test"
        )

        # Users
        self.billing_admin = User.objects.create_user(
            email="bursar@horizon.test",
            password="Password123!",
            first_name="Victor",
            last_name="Lang",
        )
        self.student = User.objects.create_user(
            email="student@horizon.test",
            password="Password123!",
            first_name="Clara",
            last_name="Oswald",
        )
        self.platform_admin = User.objects.create_superuser(
            email="super@avenor.test",
            password="Password123!",
            first_name="Avenor",
            last_name="Operations"
        )

        # Role & Membership for Billing Admin
        self.admin_role, _ = Role.objects.get_or_create(
            slug='institutional_admin',
            defaults={'name': 'Institutional Administrator'}
        )
        self.membership = TenantMembership.objects.create(
            tenant=self.tenant,
            user=self.billing_admin,
            status=MembershipStatus.ACTIVE
        )
        MembershipRole.objects.create(membership=self.membership, role=self.admin_role)

        # Plans
        self.starter_plan = SubscriptionPlan.objects.create(
            name="Starter Academy",
            slug="starter-academy",
            tier=SubscriptionTier.STARTER,
            description="Starter plan",
            price_monthly=Decimal("499.00"),
            price_annual=Decimal("4990.00"),
            currency="USD",
            max_active_scholars=500,
            max_faculty_seats=20,
            max_storage_gb=50,
            is_active=True,
            is_public=True,
        )
        self.pro_plan = SubscriptionPlan.objects.create(
            name="Professional Institute",
            slug="professional-institute",
            tier=SubscriptionTier.PROFESSIONAL,
            description="Professional plan",
            price_monthly=Decimal("1499.00"),
            price_annual=Decimal("14990.00"),
            currency="USD",
            max_active_scholars=2500,
            max_faculty_seats=100,
            max_storage_gb=250,
            is_active=True,
            is_public=True,
        )
        self.hidden_plan = SubscriptionPlan.objects.create(
            name="Special Pilot Plan",
            slug="special-pilot",
            tier=SubscriptionTier.CUSTOM,
            price_monthly=Decimal("99.00"),
            price_annual=Decimal("990.00"),
            is_active=True,
            is_public=False,
        )

        # Initial Subscription
        now = timezone.now()
        self.subscription = TenantSubscription.objects.create(
            tenant=self.tenant,
            plan=self.starter_plan,
            billing_cycle=BillingCycle.ANNUAL,
            status=SubscriptionStatus.ACTIVE,
            current_period_start=now,
            current_period_end=now + timezone.timedelta(days=365)
        )

    def test_public_plan_listing(self):
        # Anonymous user can list public active plans
        resp = self.client.get("/api/v1/finance/plans/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        results = resp.data.get('results', resp.data) if isinstance(resp.data, dict) else resp.data
        self.assertEqual(len(results), 2)  # only starter and pro, hidden_plan excluded

        # Platform Admin can see all plans including non-public
        self.client.force_authenticate(user=self.platform_admin)
        resp_admin = self.client.get("/api/v1/finance/plans/")
        results_admin = resp_admin.data.get('results', resp_admin.data) if isinstance(resp_admin.data, dict) else resp_admin.data
        self.assertEqual(len(results_admin), 3)

    def test_tenant_subscription_current_and_seat_limits(self):
        # Student cannot access billing endpoints (403 Forbidden)
        self.client.force_authenticate(user=self.student)
        resp_forbidden = self.client.get(
            "/api/v1/finance/subscription/current/",
            HTTP_HOST=f"{self.tenant.slug}.avenor.test"
        )
        self.assertEqual(resp_forbidden.status_code, status.HTTP_403_FORBIDDEN)

        # Institutional Admin can view subscription details
        self.client.force_authenticate(user=self.billing_admin)
        resp = self.client.get(
            "/api/v1/finance/subscription/current/",
            HTTP_HOST=f"{self.tenant.slug}.avenor.test"
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['plan']['slug'], 'starter-academy')
        self.assertTrue(resp.data['is_active'])
        self.assertIn('seat_limits', resp.data)
        self.assertEqual(resp.data['seat_limits']['limit'], 500)

    def test_subscription_tier_upgrade_and_invoice_issuance(self):
        self.client.force_authenticate(user=self.billing_admin)
        upgrade_url = "/api/v1/finance/subscription/change-plan/"

        resp = self.client.post(
            upgrade_url,
            {
                'plan_id': str(self.pro_plan.id),
                'billing_cycle': BillingCycle.ANNUAL,
            },
            format='json',
            HTTP_HOST=f"{self.tenant.slug}.avenor.test"
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['subscription']['plan']['slug'], 'professional-institute')

        # Check newly created invoice
        inv_data = resp.data['invoice']
        self.assertEqual(Decimal(inv_data['amount_due']), Decimal("14990.00"))
        self.assertEqual(inv_data['status'], InvoiceStatus.OPEN)

        # Verify DB persisted changes
        self.subscription.refresh_from_db()
        self.assertEqual(self.subscription.plan, self.pro_plan)

    def test_subscription_cancellation_and_reactivation_flow(self):
        self.client.force_authenticate(user=self.billing_admin)

        # Cancel at period end
        cancel_resp = self.client.post(
            "/api/v1/finance/subscription/cancel/",
            HTTP_HOST=f"{self.tenant.slug}.avenor.test"
        )
        self.assertEqual(cancel_resp.status_code, status.HTTP_200_OK)
        self.assertTrue(cancel_resp.data['cancel_at_period_end'])

        self.subscription.refresh_from_db()
        self.assertTrue(self.subscription.cancel_at_period_end)

        # Reactivate
        reactivate_resp = self.client.post(
            "/api/v1/finance/subscription/reactivate/",
            HTTP_HOST=f"{self.tenant.slug}.avenor.test"
        )
        self.assertEqual(reactivate_resp.status_code, status.HTTP_200_OK)
        self.assertFalse(reactivate_resp.data['cancel_at_period_end'])

        self.subscription.refresh_from_db()
        self.assertFalse(self.subscription.cancel_at_period_end)

    def test_invoice_listing_and_settlement(self):
        now = timezone.now()
        invoice = Invoice.objects.create(
            tenant=self.tenant,
            subscription=self.subscription,
            invoice_number='INV-TEST-2026-001',
            amount_due=Decimal('4990.00'),
            currency='USD',
            status=InvoiceStatus.OPEN,
            due_date=(now + timezone.timedelta(days=14)).date(),
        )

        self.client.force_authenticate(user=self.billing_admin)

        # List invoices
        list_resp = self.client.get(
            "/api/v1/finance/invoices/",
            HTTP_HOST=f"{self.tenant.slug}.avenor.test"
        )
        self.assertEqual(list_resp.status_code, status.HTTP_200_OK)
        results = list_resp.data.get('results', list_resp.data) if isinstance(list_resp.data, dict) else list_resp.data
        self.assertEqual(len(results), 1)

        # Pay invoice
        pay_url = f"/api/v1/finance/invoices/{invoice.id}/pay/"
        pay_resp = self.client.post(pay_url, HTTP_HOST=f"{self.tenant.slug}.avenor.test")
        self.assertEqual(pay_resp.status_code, status.HTTP_200_OK)
        self.assertEqual(pay_resp.data['invoice']['status'], InvoiceStatus.PAID)

        # Check transaction was recorded
        invoice.refresh_from_db()
        self.assertEqual(invoice.status, InvoiceStatus.PAID)
        self.assertEqual(invoice.amount_paid, Decimal('4990.00'))
        self.assertIsNotNone(invoice.paid_at)

        txns = Transaction.objects.filter(invoice=invoice)
        self.assertEqual(txns.count(), 1)
        self.assertEqual(txns.first().status, TransactionStatus.SUCCEEDED)

    def test_unified_webhook_payment_success(self):
        now = timezone.now()
        invoice = Invoice.objects.create(
            tenant=self.tenant,
            subscription=self.subscription,
            invoice_number='INV-HOOK-2026-001',
            amount_due=Decimal('1200.00'),
            currency='USD',
            status=InvoiceStatus.OPEN,
            due_date=(now + timezone.timedelta(days=7)).date(),
        )

        # Webhook post
        resp = self.client.post(
            "/api/v1/finance/webhook/",
            {
                'type': 'invoice.payment_succeeded',
                'data': {
                    'invoice_id': str(invoice.id)
                }
            },
            format='json'
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

        invoice.refresh_from_db()
        self.assertEqual(invoice.status, InvoiceStatus.PAID)
