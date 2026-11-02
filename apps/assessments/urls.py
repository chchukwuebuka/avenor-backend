from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import QuizViewSet, AssignmentViewSet, CertificateViewSet

router = DefaultRouter()
router.register('quizzes', QuizViewSet, basename='quiz')
router.register('assignments', AssignmentViewSet, basename='assignment')
router.register('certificates', CertificateViewSet, basename='certificate')

urlpatterns = [
    path('', include(router.urls)),
]
