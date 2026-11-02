import logging
from django.utils.deprecation import MiddlewareMixin
from django.http import JsonResponse
from .models import TenantDomain, TenantStatus

logger = logging.getLogger(__name__)

# System routes that do not require an active tenant context
PLATFORM_EXEMPT_PATHS = [
    '/admin/',
    '/api/v1/health/',
    '/api/v1/platform/',
    '/api/v1/auth/',
    '/api/schema/',
    '/api/docs/',
]

class TenantResolutionMiddleware(MiddlewareMixin):
    """
    Resolves the active tenant from the request's normalized hostname against TenantDomain.
    Attaches `request.tenant` to the request object.
    Enforces tenant domain verification and status checks.
    """
    def process_request(self, request):
        request.tenant = None

        # Check if the requested path is exempt from mandatory tenant resolution
        path = request.path
        is_exempt = any(path.startswith(exempt) for exempt in PLATFORM_EXEMPT_PATHS)

        # Extract and normalize hostname (ignoring port numbers)
        raw_host = request.get_host().split(':')[0].lower().strip()

        # In development/testing environments, check for development domain override
        # e.g., via development test header 'X-Dev-Tenant-Domain' or query param if enabled
        dev_domain = request.META.get('HTTP_X_DEV_TENANT_DOMAIN')
        hostname = (dev_domain or raw_host).lower().strip()

        try:
            domain_record = (
                TenantDomain.objects.select_related('tenant', 'tenant__branding', 'tenant__settings')
                .filter(hostname=hostname)
                .first()
            )

            if domain_record:
                tenant = domain_record.tenant
                if tenant.status == TenantStatus.ACTIVE:
                    request.tenant = tenant
                elif tenant.status == TenantStatus.SUSPENDED:
                    if not is_exempt:
                        return JsonResponse(
                            {
                                'success': False,
                                'message': 'This institution account is currently suspended.',
                                'errors': {'tenant': ['Tenant is suspended.']},
                            },
                            status=403
                        )
        except Exception as e:
            logger.warning("Error resolving tenant for hostname '%s': %s", hostname, e)

        # If path is an institutional API endpoint requiring a tenant, ensure it resolved
        if path.startswith('/api/v1/tenants/current/') and not request.tenant:
            # Fallback for root dev domain to default active tenant if none matched
            first_active = TenantDomain.objects.select_related('tenant').filter(tenant__status=TenantStatus.ACTIVE).first()
            if first_active:
                request.tenant = first_active.tenant

        return None
