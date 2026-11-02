import uuid
from decimal import Decimal
from django.db import models
from django.utils import timezone
from apps.tenants.models import Tenant, TenantModel


class SubscriptionTier(models.TextChoices):
    STARTER = 'starter', 'Starter Academy'
    PROFESSIONAL = 'professional', 'Professional Institute'
    ENTERPRISE = 'enterprise', 'Enterprise University'
    CUSTOM = 'custom', 'Custom Consortium'


class SubscriptionStatus(models.TextChoices):
    TRIALING = 'trialing', 'Trialing'
    ACTIVE = 'active', 'Active'
    PAST_DUE = 'past_due', 'Past Due'
    CANCELED = 'canceled', 'Canceled'
    UNPAID = 'unpaid', 'Unpaid'
    INCOMPLETE = 'incomplete', 'Incomplete'


class BillingCycle(models.TextChoices):
    MONTHLY = 'monthly', 'Monthly'
    ANNUAL = 'annual', 'Annual'


class InvoiceStatus(models.TextChoices):
    DRAFT = 'draft', 'Draft'
    OPEN = 'open', 'Open'
    PAID = 'paid', 'Paid'
    UNCOLLECTIBLE = 'uncollectible', 'Uncollectible'
    VOID = 'void', 'Void'


class PaymentGateway(models.TextChoices):
    STRIPE = 'stripe', 'Stripe'
    PAYSTACK = 'paystack', 'Paystack'
    WIRE_TRANSFER = 'wire_transfer', 'Wire Transfer'
    MANUAL = 'manual', 'Manual Reconciliation'


class TransactionStatus(models.TextChoices):
    PENDING = 'pending', 'Pending'
    SUCCEEDED = 'succeeded', 'Succeeded'
    FAILED = 'failed', 'Failed'
    REFUNDED = 'refunded', 'Refunded'


class SubscriptionPlan(models.Model):
    """
    Platform-wide subscription tier plans for tenant institutions.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=150)
    slug = models.SlugField(max_length=100, unique=True, db_index=True)
    tier = models.CharField(max_length=50, choices=SubscriptionTier.choices, default=SubscriptionTier.PROFESSIONAL)
    description = models.TextField(blank=True, default='')

    price_monthly = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    price_annual = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    currency = models.CharField(max_length=10, default='USD')

    max_active_scholars = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Maximum concurrently active scholars. Null implies unlimited."
    )
    max_faculty_seats = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Maximum faculty and lecturer seats. Null implies unlimited."
    )
    max_storage_gb = models.PositiveIntegerField(
        default=50,
        help_text="Cloud asset storage allocation in gigabytes."
    )

    features = models.JSONField(
        default=dict,
        blank=True,
        help_text="Feature flags (e.g. white_label, custom_domain, sso, api_access, etc.)"
    )

    is_active = models.BooleanField(default=True)
    is_public = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Subscription Plan'
        verbose_name_plural = 'Subscription Plans'
        ordering = ['price_monthly']

    def __str__(self):
        return f"{self.name} ({self.get_tier_display()}) — {self.currency} {self.price_monthly}/mo"


class TenantSubscription(TenantModel):
    """
    Active SaaS subscription agreement for a tenant institution.
    """
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='finance_subscriptions')
    plan = models.ForeignKey(SubscriptionPlan, on_delete=models.PROTECT, related_name='tenant_subscriptions')
    billing_cycle = models.CharField(max_length=20, choices=BillingCycle.choices, default=BillingCycle.ANNUAL)
    status = models.CharField(max_length=30, choices=SubscriptionStatus.choices, default=SubscriptionStatus.ACTIVE)

    current_period_start = models.DateTimeField(default=timezone.now)
    current_period_end = models.DateTimeField()
    cancel_at_period_end = models.BooleanField(default=False)
    trial_ends_at = models.DateTimeField(null=True, blank=True)

    gateway_customer_id = models.CharField(max_length=128, blank=True, default='')
    gateway_subscription_id = models.CharField(max_length=128, blank=True, default='')

    class Meta:
        verbose_name = 'Tenant Subscription'
        verbose_name_plural = 'Tenant Subscriptions'
        ordering = ['-current_period_end']

    def __str__(self):
        return f"{self.tenant.name} — {self.plan.name} ({self.status})"

    def is_active_subscription(self):
        if self.status in [SubscriptionStatus.ACTIVE, SubscriptionStatus.TRIALING]:
            if self.current_period_end:
                return self.current_period_end >= timezone.now()
            return True
        return False

    def days_until_renewal(self):
        if not self.current_period_end:
            return None
        delta = self.current_period_end - timezone.now()
        return max(0, delta.days)

    def check_seat_limit(self, active_scholars_count):
        limit = self.plan.max_active_scholars
        if limit is None:
            return {'allowed': True, 'limit': None, 'current': active_scholars_count, 'remaining': None}
        return {
            'allowed': active_scholars_count < limit,
            'limit': limit,
            'current': active_scholars_count,
            'remaining': max(0, limit - active_scholars_count),
        }


class Invoice(TenantModel):
    """
    Billing invoice issued to an institution.
    """
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='finance_invoices')
    subscription = models.ForeignKey(
        TenantSubscription,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='invoices'
    )
    invoice_number = models.CharField(max_length=64, unique=True, db_index=True)
    amount_due = models.DecimalField(max_digits=12, decimal_places=2)
    amount_paid = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    currency = models.CharField(max_length=10, default='USD')
    status = models.CharField(max_length=30, choices=InvoiceStatus.choices, default=InvoiceStatus.OPEN)

    due_date = models.DateField()
    paid_at = models.DateTimeField(null=True, blank=True)
    line_items = models.JSONField(
        default=list,
        blank=True,
        help_text="Detailed itemized breakdown: [{'description': '...', 'quantity': 1, 'unit_price': '...', 'total': '...'}]"
    )
    pdf_receipt_url = models.CharField(max_length=512, blank=True, default='')
    notes = models.TextField(blank=True, default='')

    class Meta:
        verbose_name = 'Invoice'
        verbose_name_plural = 'Invoices'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.invoice_number} ({self.tenant.slug}) — {self.currency} {self.amount_due} [{self.status}]"

    def mark_as_paid(self, paid_amount=None):
        self.status = InvoiceStatus.PAID
        self.amount_paid = paid_amount if paid_amount is not None else self.amount_due
        self.paid_at = timezone.now()
        self.save(update_fields=['status', 'amount_paid', 'paid_at', 'updated_at'])


class Transaction(TenantModel):
    """
    Recorded gateway payment transaction or wire reconciliation.
    """
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='finance_transactions')
    invoice = models.ForeignKey(
        Invoice,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='transactions'
    )
    reference = models.CharField(max_length=128, unique=True, db_index=True)
    gateway = models.CharField(max_length=30, choices=PaymentGateway.choices, default=PaymentGateway.STRIPE)
    gateway_reference = models.CharField(max_length=255, blank=True, default='')

    amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=10, default='USD')
    status = models.CharField(max_length=30, choices=TransactionStatus.choices, default=TransactionStatus.SUCCEEDED)
    payment_method_type = models.CharField(max_length=50, default='card')

    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        verbose_name = 'Transaction'
        verbose_name_plural = 'Transactions'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.reference} — {self.currency} {self.amount} via {self.gateway} [{self.status}]"
