import uuid
from decimal import Decimal
from django.utils import timezone
from rest_framework import viewsets, status, permissions
from rest_framework.exceptions import PermissionDenied, NotFound, ValidationError
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from drf_spectacular.utils import extend_schema, OpenApiParameter

from apps.tenants.models import Tenant
from .models import (
    SubscriptionPlan,
    TenantSubscription,
    Invoice,
    Transaction,
    SubscriptionStatus,
    InvoiceStatus,
    PaymentGateway,
    TransactionStatus,
    BillingCycle,
)
from .serializers import (
    SubscriptionPlanSerializer,
    TenantSubscriptionSerializer,
    ChangePlanSerializer,
    InvoiceSerializer,
    TransactionSerializer,
)


def get_request_tenant(request):
    tenant = getattr(request, 'tenant', None)
    if not tenant and request.user.is_authenticated:
        membership = request.user.tenant_memberships.first()
        if membership:
            tenant = membership.tenant
        else:
            tenant = Tenant.objects.first()
    return tenant


def is_billing_admin(user, tenant=None):
    if not user.is_authenticated:
        return False
    if user.is_staff or user.is_superuser:
        return True
    qs = user.tenant_memberships.filter(
        roles__slug__in=['institutional_admin', 'billing_manager', 'dean']
    )
    if tenant:
        qs = qs.filter(tenant=tenant)
    return qs.exists()


class SubscriptionPlanViewSet(viewsets.ModelViewSet):
    """
    SaaS Tier Plans available across the Avenor platform.
    Publicly browsable; editable by platform operations administrators.
    """
    queryset = SubscriptionPlan.objects.all()
    serializer_class = SubscriptionPlanSerializer

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            return [permissions.AllowAny()]
        return [permissions.IsAdminUser()]

    def get_queryset(self):
        user = self.request.user
        if user.is_authenticated and (user.is_staff or user.is_superuser):
            return SubscriptionPlan.objects.all()
        return SubscriptionPlan.objects.filter(is_active=True, is_public=True)


class TenantSubscriptionViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Institutional subscription governance, tier upgrades, and renewal statuses.
    """
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = TenantSubscriptionSerializer

    def get_queryset(self):
        tenant = get_request_tenant(self.request)
        if not tenant:
            return TenantSubscription.objects.none()
        return TenantSubscription.objects.filter(tenant=tenant).select_related('plan', 'tenant')

    @extend_schema(summary="Get current tenant active subscription")
    @action(detail=False, methods=['get'], url_path='current')
    def current(self, request):
        tenant = get_request_tenant(request)
        if not tenant:
            raise NotFound("No active institutional tenant context found.")

        if not is_billing_admin(request.user, tenant):
            raise PermissionDenied("Institutional administrator or billing manager privileges required.")

        sub = TenantSubscription.objects.filter(tenant=tenant).order_by('-created_at').first()
        if not sub:
            # Auto-provision starter trialing plan if none exists
            default_plan = SubscriptionPlan.objects.filter(slug='starter-academy').first() or SubscriptionPlan.objects.first()
            if default_plan:
                now = timezone.now()
                sub = TenantSubscription.objects.create(
                    tenant=tenant,
                    plan=default_plan,
                    billing_cycle=BillingCycle.ANNUAL,
                    status=SubscriptionStatus.ACTIVE,
                    current_period_start=now,
                    current_period_end=now + timezone.timedelta(days=365)
                )

        if not sub:
            return Response({'detail': 'No active subscription plan found.'}, status=status.HTTP_404_NOT_FOUND)

        return Response(TenantSubscriptionSerializer(sub, context={'request': request}).data)

    @extend_schema(summary="Change or upgrade institutional subscription tier", request=ChangePlanSerializer)
    @action(detail=False, methods=['post'], url_path='change-plan')
    def change_plan(self, request):
        tenant = get_request_tenant(request)
        if not tenant:
            raise NotFound("No active institutional tenant context found.")

        if not is_billing_admin(request.user, tenant):
            raise PermissionDenied("Administrative privileges required to modify institutional subscription tier.")

        serializer = ChangePlanSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        plan_id = serializer.validated_data['plan_id']
        billing_cycle = serializer.validated_data.get('billing_cycle', BillingCycle.ANNUAL)

        try:
            new_plan = SubscriptionPlan.objects.get(id=plan_id, is_active=True)
        except SubscriptionPlan.DoesNotExist:
            raise ValidationError({'plan_id': 'Invalid or inactive subscription plan selected.'})

        now = timezone.now()
        period_days = 365 if billing_cycle == BillingCycle.ANNUAL else 30

        sub = TenantSubscription.objects.filter(tenant=tenant).order_by('-created_at').first()
        if sub:
            sub.plan = new_plan
            sub.billing_cycle = billing_cycle
            sub.status = SubscriptionStatus.ACTIVE
            sub.cancel_at_period_end = False
            sub.current_period_start = now
            sub.current_period_end = now + timezone.timedelta(days=period_days)
            sub.save()
        else:
            sub = TenantSubscription.objects.create(
                tenant=tenant,
                plan=new_plan,
                billing_cycle=billing_cycle,
                status=SubscriptionStatus.ACTIVE,
                current_period_start=now,
                current_period_end=now + timezone.timedelta(days=period_days)
            )

        # Generate subscription invoice
        price = new_plan.price_annual if billing_cycle == BillingCycle.ANNUAL else new_plan.price_monthly
        inv_number = f"INV-{now.strftime('%Y%m')}-{tenant.slug[:8].upper()}-{str(uuid.uuid4())[:4].upper()}"

        invoice = Invoice.objects.create(
            tenant=tenant,
            subscription=sub,
            invoice_number=inv_number,
            amount_due=price,
            amount_paid=Decimal('0.00'),
            currency=new_plan.currency,
            status=InvoiceStatus.OPEN if price > 0 else InvoiceStatus.PAID,
            due_date=(now + timezone.timedelta(days=14)).date(),
            paid_at=now if price == 0 else None,
            line_items=[{
                'description': f"{new_plan.name} ({billing_cycle.title()}) License Allocation",
                'quantity': 1,
                'unit_price': str(price),
                'total': str(price),
            }],
            notes=f"Tier change to {new_plan.name} effective immediately."
        )

        return Response({
            'subscription': TenantSubscriptionSerializer(sub, context={'request': request}).data,
            'invoice': InvoiceSerializer(invoice).data,
            'message': f"Successfully upgraded subscription to {new_plan.name}."
        }, status=status.HTTP_200_OK)

    @extend_schema(summary="Set subscription to cancel at end of current period")
    @action(detail=False, methods=['post'], url_path='cancel')
    def cancel_subscription(self, request):
        tenant = get_request_tenant(request)
        if not is_billing_admin(request.user, tenant):
            raise PermissionDenied("Administrative privileges required to cancel institutional subscription.")

        sub = TenantSubscription.objects.filter(tenant=tenant).order_by('-created_at').first()
        if not sub:
            raise NotFound("No active subscription found to cancel.")

        sub.cancel_at_period_end = True
        sub.save(update_fields=['cancel_at_period_end', 'updated_at'])
        return Response({
            'message': 'Subscription set to terminate at the conclusion of the billing cycle.',
            'cancel_at_period_end': True,
            'renewal_date': sub.current_period_end,
        }, status=status.HTTP_200_OK)

    @extend_schema(summary="Reactivate subscription scheduled for cancellation")
    @action(detail=False, methods=['post'], url_path='reactivate')
    def reactivate_subscription(self, request):
        tenant = get_request_tenant(request)
        if not is_billing_admin(request.user, tenant):
            raise PermissionDenied("Administrative privileges required.")

        sub = TenantSubscription.objects.filter(tenant=tenant).order_by('-created_at').first()
        if not sub:
            raise NotFound("No active subscription found.")

        sub.cancel_at_period_end = False
        sub.save(update_fields=['cancel_at_period_end', 'updated_at'])
        return Response({
            'message': 'Subscription auto-renewal reinstated successfully.',
            'cancel_at_period_end': False,
        }, status=status.HTTP_200_OK)


class InvoiceViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Billing invoices and receipts issued to the institution.
    """
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = InvoiceSerializer

    def get_queryset(self):
        tenant = get_request_tenant(self.request)
        if not tenant:
            return Invoice.objects.none()
        return Invoice.objects.filter(tenant=tenant).order_by('-created_at')

    @extend_schema(summary="Settle/Pay an open invoice")
    @action(detail=True, methods=['post'], url_path='pay')
    def pay_invoice(self, request, pk=None):
        tenant = get_request_tenant(request)
        if not is_billing_admin(request.user, tenant):
            raise PermissionDenied("Billing officer privileges required to settle invoices.")

        invoice = self.get_object()
        if invoice.status == InvoiceStatus.PAID:
            return Response({'detail': 'This invoice has already been settled in full.'}, status=status.HTTP_400_BAD_REQUEST)

        # Mark paid and record transaction
        now = timezone.now()
        invoice.mark_as_paid()

        txn_ref = f"TXN-{now.strftime('%Y%m%d')}-{uuid.uuid4().hex[:12].upper()}"
        txn = Transaction.objects.create(
            tenant=invoice.tenant,
            invoice=invoice,
            reference=txn_ref,
            gateway=PaymentGateway.STRIPE,
            gateway_reference=f"ch_{uuid.uuid4().hex[:18]}",
            amount=invoice.amount_due,
            currency=invoice.currency,
            status=TransactionStatus.SUCCEEDED,
            payment_method_type='card',
            metadata={'settled_by': request.user.email, 'timestamp': now.isoformat()}
        )

        return Response({
            'message': 'Invoice successfully settled.',
            'invoice': InvoiceSerializer(invoice).data,
            'transaction': TransactionSerializer(txn).data,
        }, status=status.HTTP_200_OK)


class TransactionViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Audit ledger of all payment transactions and gateway settlements.
    """
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = TransactionSerializer

    def get_queryset(self):
        tenant = get_request_tenant(self.request)
        if not tenant:
            return Transaction.objects.none()
        return Transaction.objects.filter(tenant=tenant).order_by('-created_at')


class UnifiedWebhookView(APIView):
    """
    Unified payment gateway webhook handler for Stripe, Paystack, and bank wire updates.
    """
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        event_type = request.data.get('event') or request.data.get('type')
        data = request.data.get('data', {})

        # Process payment success callback
        if event_type in ['charge.success', 'payment_intent.succeeded', 'invoice.payment_succeeded']:
            invoice_id = data.get('invoice_id')
            if invoice_id:
                inv = Invoice.objects.filter(id=invoice_id).first()
                if inv and inv.status != InvoiceStatus.PAID:
                    inv.mark_as_paid()

        return Response({'status': 'webhook received', 'event': event_type}, status=status.HTTP_200_OK)
