from django.urls import path
from .views import (
    PublicCourseListView,
    PublicCourseDetailView,
    PublicProgrammeListView,
    FacultyCourseListCreateView,
    FacultyCourseDetailView,
    FacultyCoursePublishView,
    FacultyModuleCreateView,
    FacultyLessonCreateView,
    FacultyCohortCreateView,
)

urlpatterns = [
    # Public Course & Programme Catalogue
    path('', PublicCourseListView.as_view(), name='course-public-list'),
    path('programmes/', PublicProgrammeListView.as_view(), name='programme-public-list'),

    # Faculty & Administrative Authoring Endpoints (Avenor Admin)
    path('manage/', FacultyCourseListCreateView.as_view(), name='course-manage-list-create'),
    path('manage/<uuid:pk>/', FacultyCourseDetailView.as_view(), name='course-manage-detail'),
    path('manage/<uuid:pk>/publish/', FacultyCoursePublishView.as_view(), name='course-manage-publish'),
    path('manage/<uuid:pk>/modules/', FacultyModuleCreateView.as_view(), name='course-manage-add-module'),
    path('manage/modules/<uuid:module_id>/lessons/', FacultyLessonCreateView.as_view(), name='course-manage-add-lesson'),
    path('manage/<uuid:pk>/cohorts/', FacultyCohortCreateView.as_view(), name='course-manage-add-cohort'),

    # Public Course Detail (Placed last to prevent slug collision with programmes/manage)
    path('<slug:slug>/', PublicCourseDetailView.as_view(), name='course-public-detail'),
]
