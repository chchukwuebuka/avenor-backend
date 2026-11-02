import uuid
from django.db import models
from django.core.exceptions import ValidationError

class InstitutionType(models.TextChoices):
    UNIVERSITY = 'university', 'University'
    POLYTECHNIC = 'polytechnic', 'Polytechnic'
    PROFESSIONAL_TRAINING = 'professional_training', 'Professional Training'
    COLLEGE = 'college', 'College'
    CORPORATE_LEARNING = 'corporate_learning', 'Corporate Learning'

class TenantStatus(models.TextChoices):
    PENDING = 'pending', 'Pending'
    ACTIVE = 'active', 'Active'
    SUSPENDED = 'suspended', 'Suspended'
    ARCHIVED = 'archived', 'Archived'

class Tenant(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=100, unique=True, db_index=True)
    institution_type = models.CharField(
        max_length=50,
        choices=InstitutionType.choices,
        default=InstitutionType.PROFESSIONAL_TRAINING
    )
    description = models.TextField(blank=True, default='')
    status = models.CharField(
        max_length=20,
        choices=TenantStatus.choices,
        default=TenantStatus.ACTIVE
    )
    timezone = models.CharField(max_length=50, default='UTC')
    default_currency = models.CharField(max_length=10, default='USD')
    contact_email = models.EmailField()
    contact_phone = models.CharField(max_length=32, blank=True, default='')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Tenant'
        verbose_name_plural = 'Tenants'
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.slug})"

    def clean(self):
        self.slug = self.slug.lower()

class TenantDomain(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='domains')
    hostname = models.CharField(max_length=255, unique=True, db_index=True)
    is_primary = models.BooleanField(default=False)
    is_verified = models.BooleanField(default=False)
    verification_token = models.CharField(max_length=64, default=uuid.uuid4)
    verified_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Tenant Domain'
        verbose_name_plural = 'Tenant Domains'
        ordering = ['-is_primary', 'hostname']

    def __str__(self):
        return f"{self.hostname} -> {self.tenant.slug}"

    def clean(self):
        self.hostname = self.hostname.lower().strip()
        if self.is_primary:
            # Ensure only one primary domain exists per tenant
            TenantDomain.objects.filter(tenant=self.tenant, is_primary=True).exclude(pk=self.pk).update(is_primary=False)

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

class TenantBranding(models.Model):
    tenant = models.OneToOneField(Tenant, on_delete=models.CASCADE, related_name='branding', primary_key=True)
    site_name = models.CharField(max_length=255)
    logo = models.ImageField(upload_to='tenant_logos/', blank=True, null=True)
    favicon = models.ImageField(upload_to='tenant_favicons/', blank=True, null=True)

    # Theme Tokens (validated CSS colours)
    primary_colour = models.CharField(max_length=16, default='#111111')
    secondary_colour = models.CharField(max_length=16, default='#F5F5F5')
    accent_colour = models.CharField(max_length=16, default='#111111')
    background_colour = models.CharField(max_length=16, default='#FFFFFF')
    text_colour = models.CharField(max_length=16, default='#111111')

    # Typography
    heading_font = models.CharField(max_length=64, default='Sora')
    body_font = models.CharField(max_length=64, default='Manrope')

    # Contact & Footer
    support_email = models.EmailField(blank=True, default='')
    support_phone = models.CharField(max_length=32, blank=True, default='')
    footer_text = models.TextField(blank=True, default='')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Tenant Branding'
        verbose_name_plural = 'Tenant Brandings'

    def __str__(self):
        return f"Branding: {self.site_name} ({self.tenant.slug})"

class TenantSettings(models.Model):
    tenant = models.OneToOneField(Tenant, on_delete=models.CASCADE, related_name='settings', primary_key=True)
    public_registration_enabled = models.BooleanField(default=True)
    applications_enabled = models.BooleanField(default=True)
    learner_registration_enabled = models.BooleanField(default=True)
    certificates_enabled = models.BooleanField(default=True)
    payment_enabled = models.BooleanField(default=True)
    public_course_catalogue_enabled = models.BooleanField(default=True)
    maintenance_message = models.TextField(blank=True, default='')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Tenant Settings'
        verbose_name_plural = 'Tenant Settings'

    def __str__(self):
        return f"Settings: {self.tenant.slug}"

class TenantQuerySet(models.QuerySet):
    def for_tenant(self, tenant):
        if not tenant:
            return self.none()
        return self.filter(tenant=tenant)

class TenantManager(models.Manager):
    def get_queryset(self):
        return TenantQuerySet(self.model, using=self._db)

    def for_tenant(self, tenant):
        return self.get_queryset().for_tenant(tenant)

class TenantModel(models.Model):
    """
    Abstract base model for all tenant-scoped business entities
    (Programmes, Courses, Enrolments, Payments, etc.)
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        related_name='%(app_label)s_%(class)s_related',
        db_index=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = TenantManager()

    class Meta:
        abstract = True
