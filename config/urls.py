from django.contrib import admin
from django.urls import path, include
from django.http import JsonResponse
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

from django.utils import timezone
from django.db import connection
from django.core.cache import cache

def healthz(request):
    """Aggregated health check for container runtimes."""
    return JsonResponse({
        'status': 'healthy',
        'platform': 'AVENOR SaaS API',
        'version': '1.0.0',
        'timestamp': timezone.now().isoformat(),
    })

def livez(request):
    """Liveness probe: verifies process responsiveness."""
    return JsonResponse({
        'status': 'alive',
        'timestamp': timezone.now().isoformat(),
    })

def readyz(request):
    """Readiness probe: verifies database and cache connectivity."""
    checks = {}
    is_ready = True

    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1;")
            cursor.fetchone()
        checks['database'] = 'connected'
    except Exception as e:
        checks['database'] = f'error: {str(e)}'
        is_ready = False

    try:
        cache.set('__readyz_check__', 'ok', timeout=10)
        val = cache.get('__readyz_check__')
        checks['cache'] = 'connected' if val == 'ok' else 'degraded'
    except Exception as e:
        checks['cache'] = f'warning: {str(e)}'

    status_code = 200 if is_ready else 503
    return JsonResponse({
        'status': 'ready' if is_ready else 'not_ready',
        'checks': checks,
        'timestamp': timezone.now().isoformat(),
    }, status=status_code)

def health_check(request):
    return healthz(request)

urlpatterns = [
    path('healthz/', healthz, name='healthz'),
    path('livez/', livez, name='livez'),
    path('readyz/', readyz, name='readyz'),
    path('admin/', admin.site.urls),
    path('api/v1/health/', health_check, name='health-check'),
    path('api/v1/auth/', include('apps.accounts.urls')),
    path('api/v1/tenants/', include('apps.tenants.urls')),
    path('api/v1/members/', include('apps.memberships.urls')),
    path('api/v1/courses/', include('apps.courses.urls')),
    path('api/v1/enrollments/', include('apps.enrollments.urls')),
    path('api/v1/assessments/', include('apps.assessments.urls')),
    path('api/v1/communications/', include('apps.communications.urls')),
    path('api/v1/finance/', include('apps.finance.urls')),
    path('api/v1/analytics/', include('apps.analytics.urls')),
    
    # OpenAPI Schema & Swagger UI
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
]
