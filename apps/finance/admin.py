from django.contrib import admin
from .models import (
    SubscriptionPlan,
    TenantSubscription,
    Invoice,
    Transaction,
)


@admin.register(SubscriptionPlan)
class SubscriptionPlanAdmin(admin.ModelAdmin):
    list_display = ('name', 'tier', 'currency', 'price_monthly', 'price_annual', 'max_active_scholars', 'is_active', 'is_public')
    list_filter = ('tier', 'currency', 'is_active', 'is_public')
    search_fields = ('name', 'slug', 'description')
    prepopulated_fields = {'slug': ('name',)}


@admin.register(TenantSubscription)
class TenantSubscriptionAdmin(admin.ModelAdmin):
    list_display = ('tenant', 'plan', 'billing_cycle', 'status', 'current_period_end', 'cancel_at_period_end')
    list_filter = ('billing_cycle', 'status', 'cancel_at_period_end')
    search_fields = ('tenant__name', 'tenant__slug', 'gateway_customer_id', 'gateway_subscription_id')


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ('invoice_number', 'tenant', 'amount_due', 'amount_paid', 'currency', 'status', 'due_date', 'paid_at')
    list_filter = ('status', 'currency', 'due_date')
    search_fields = ('invoice_number', 'tenant__name', 'tenant__slug')


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ('reference', 'tenant', 'amount', 'currency', 'gateway', 'status', 'created_at')
    list_filter = ('gateway', 'status', 'currency')
    search_fields = ('reference', 'gateway_reference', 'tenant__name')
