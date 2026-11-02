from rest_framework import serializers
from .models import (
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


class SubscriptionPlanSerializer(serializers.ModelSerializer):
    tier_display = serializers.CharField(source='get_tier_display', read_only=True)

    class Meta:
        model = SubscriptionPlan
        fields = [
            'id',
            'name',
            'slug',
            'tier',
            'tier_display',
            'description',
            'price_monthly',
            'price_annual',
            'currency',
            'max_active_scholars',
            'max_faculty_seats',
            'max_storage_gb',
            'features',
            'is_active',
            'is_public',
            'created_at',
        ]
        read_only_fields = ['id', 'tier_display', 'created_at']


class TenantSubscriptionSerializer(serializers.ModelSerializer):
    plan = SubscriptionPlanSerializer(read_only=True)
    plan_id = serializers.PrimaryKeyRelatedField(
        queryset=SubscriptionPlan.objects.all(),
        write_only=True,
        source='plan'
    )
    is_active = serializers.BooleanField(source='is_active_subscription', read_only=True)
    days_until_renewal = serializers.IntegerField(read_only=True)
    active_scholars_count = serializers.SerializerMethodField()
    seat_limits = serializers.SerializerMethodField()

    class Meta:
        model = TenantSubscription
        fields = [
            'id',
            'tenant',
            'plan',
            'plan_id',
            'billing_cycle',
            'status',
            'current_period_start',
            'current_period_end',
            'cancel_at_period_end',
            'trial_ends_at',
            'gateway_customer_id',
            'gateway_subscription_id',
            'is_active',
            'days_until_renewal',
            'active_scholars_count',
            'seat_limits',
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'id',
            'tenant',
            'is_active',
            'days_until_renewal',
            'active_scholars_count',
            'seat_limits',
            'created_at',
            'updated_at',
        ]

    def get_active_scholars_count(self, obj):
        from apps.enrollments.models import Enrollment, EnrollmentStatus
        return Enrollment.objects.filter(
            tenant=obj.tenant,
            status=EnrollmentStatus.ACTIVE
        ).values('student').distinct().count()

    def get_seat_limits(self, obj):
        current_count = self.get_active_scholars_count(obj)
        return obj.check_seat_limit(current_count)


class ChangePlanSerializer(serializers.Serializer):
    plan_id = serializers.UUIDField(required=True)
    billing_cycle = serializers.ChoiceField(choices=BillingCycle.choices, default=BillingCycle.ANNUAL)


class InvoiceSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = Invoice
        fields = [
            'id',
            'tenant',
            'subscription',
            'invoice_number',
            'amount_due',
            'amount_paid',
            'currency',
            'status',
            'status_display',
            'due_date',
            'paid_at',
            'line_items',
            'pdf_receipt_url',
            'notes',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'tenant', 'status_display', 'created_at', 'updated_at']


class TransactionSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    gateway_display = serializers.CharField(source='get_gateway_display', read_only=True)

    class Meta:
        model = Transaction
        fields = [
            'id',
            'tenant',
            'invoice',
            'reference',
            'gateway',
            'gateway_display',
            'gateway_reference',
            'amount',
            'currency',
            'status',
            'status_display',
            'payment_method_type',
            'metadata',
            'created_at',
        ]
        read_only_fields = ['id', 'tenant', 'status_display', 'gateway_display', 'created_at']
