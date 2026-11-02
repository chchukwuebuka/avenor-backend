from django.contrib import admin
from django.urls import path, include
from django.http import JsonResponse
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

def health_check(request):
    return JsonResponse({
        'status': 'healthy',
        'platform': 'Avenor SaaS API',
        'version': '1.0.0',
        'environment': 'development'
    })

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/v1/health/', health_check, name='health-check'),
    path('api/v1/auth/', include('apps.accounts.urls')),
    path('api/v1/tenants/', include('apps.tenants.urls')),
    path('api/v1/members/', include('apps.memberships.urls')),
    path('api/v1/courses/', include('apps.courses.urls')),
    path('api/v1/enrollments/', include('apps.enrollments.urls')),
    path('api/v1/assessments/', include('apps.assessments.urls')),
    path('api/v1/communications/', include('apps.communications.urls')),
    
    # OpenAPI Schema & Swagger UI
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
]
