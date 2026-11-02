from rest_framework import generics, views, status, permissions
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.db import models
from common.permissions import IsTenantMember, IsTenantAdmin, HasTenantPermission
from .models import (
    Programme,
    Course,
    Module,
    Lesson,
    CourseOffering,
    AcademicStatus,
)
from .serializers import (
    ProgrammeSerializer,
    PublicCourseListSerializer,
    PublicCourseDetailSerializer,
    CourseCreateUpdateSerializer,
    ModuleSerializer,
    LessonSerializer,
    CourseOfferingSerializer,
)


# =========================================================================
# PUBLIC CATALOGUE ENDPOINTS (AVENOR PUBLIC)
# =========================================================================

class PublicCourseListView(generics.ListAPIView):
    """
    Public course catalogue listing published courses for the resolved tenant.
    """
    serializer_class = PublicCourseListSerializer
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        tenant = getattr(self.request, 'tenant', None)
        if not tenant:
            return Course.objects.none()

        qs = Course.objects.for_tenant(tenant)\
            .filter(status=AcademicStatus.PUBLISHED)\
            .select_related('programme', 'tenant')\
            .prefetch_related('offerings')

        # Filter by Programme
        prog_param = self.request.query_params.get('programme')
        if prog_param:
            qs = qs.filter(programme__slug=prog_param)

        # Filter by Level
        level_param = self.request.query_params.get('level')
        if level_param:
            qs = qs.filter(level=level_param)

        # Filter by Delivery Mode on Offerings
        delivery_param = self.request.query_params.get('delivery')
        if delivery_param:
            qs = qs.filter(offerings__delivery_mode=delivery_param).distinct()

        # Search Query
        search = self.request.query_params.get('search')
        if search:
            qs = qs.filter(
                models.Q(title__icontains=search) |
                models.Q(short_description__icontains=search) |
                models.Q(programme__name__icontains=search)
            )

        return qs.order_by('title')


class PublicCourseDetailView(views.APIView):
    """
    Detailed public syllabus for a specific course identified by slug.
    """
    permission_classes = [permissions.AllowAny]

    def get(self, request, slug):
        tenant = getattr(request, 'tenant', None)
        if not tenant:
            return Response(
                {'error': 'Institution not resolved for this domain.'},
                status=status.HTTP_404_NOT_FOUND
            )

        course = get_object_or_404(
            Course.objects.for_tenant(tenant).prefetch_related(
                'programme',
                'modules__lessons',
                'offerings'
            ),
            slug=slug,
            status=AcademicStatus.PUBLISHED
        )

        serializer = PublicCourseDetailSerializer(course)
        return Response({
            'success': True,
            'data': serializer.data
        })


class PublicProgrammeListView(generics.ListAPIView):
    """
    List academic programmes / departments within the resolved tenant.
    """
    serializer_class = ProgrammeSerializer
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        tenant = getattr(self.request, 'tenant', None)
        if not tenant:
            return Programme.objects.none()

        return Programme.objects.for_tenant(tenant)\
            .filter(status=AcademicStatus.PUBLISHED)\
            .order_by('name')


# =========================================================================
# FACULTY & ADMINISTRATIVE ENDPOINTS (AVENOR ADMIN)
# =========================================================================

class FacultyCourseListCreateView(views.APIView):
    """
    List all institutional courses (including drafts) or author a new course.
    """
    permission_classes = [IsTenantMember]

    def get(self, request):
        tenant = getattr(request, 'tenant', None)
        if not tenant:
            return Response([])

        qs = Course.objects.for_tenant(tenant)\
            .select_related('programme')\
            .prefetch_related('offerings')\
            .order_by('-created_at')

        status_param = request.query_params.get('status')
        if status_param:
            qs = qs.filter(status=status_param)

        return Response(PublicCourseListSerializer(qs, many=True).data)

    def post(self, request):
        tenant = getattr(request, 'tenant', None)
        if not tenant:
            return Response({'error': 'Tenant not resolved.'}, status=status.HTTP_400_BAD_REQUEST)

        # Enforce courses.create permission
        if not (request.user.is_superuser or getattr(request.user, 'is_platform_staff', False)):
            membership = getattr(request, 'membership', None)
            if not membership or not (membership.is_admin or membership.has_permission('courses.create')):
                return Response({'error': 'Permission denied.'}, status=status.HTTP_403_FORBIDDEN)

        serializer = CourseCreateUpdateSerializer(data=request.data, context={'tenant': tenant})
        serializer.is_valid(raise_exception=True)
        course = serializer.save(tenant=tenant)

        return Response(
            PublicCourseDetailSerializer(course).data,
            status=status.HTTP_201_CREATED
        )


class FacultyCourseDetailView(views.APIView):
    """
    Retrieve, update, or delete a course.
    """
    permission_classes = [IsTenantMember]

    def get_object(self, request, pk):
        tenant = getattr(request, 'tenant', None)
        return get_object_or_404(
            Course.objects.for_tenant(tenant).prefetch_related('modules__lessons', 'offerings', 'programme'),
            pk=pk
        )

    def get(self, request, pk):
        course = self.get_object(request, pk)
        return Response(PublicCourseDetailSerializer(course).data)

    def patch(self, request, pk):
        course = self.get_object(request, pk)
        tenant = getattr(request, 'tenant', None)

        if not (request.user.is_superuser or getattr(request.user, 'is_platform_staff', False)):
            membership = getattr(request, 'membership', None)
            if not membership or not (membership.is_admin or membership.has_permission('courses.edit')):
                return Response({'error': 'Permission denied.'}, status=status.HTTP_403_FORBIDDEN)

        serializer = CourseCreateUpdateSerializer(course, data=request.data, partial=True, context={'tenant': tenant})
        serializer.is_valid(raise_exception=True)
        updated = serializer.save()

        return Response(PublicCourseDetailSerializer(updated).data)

    def delete(self, request, pk):
        course = self.get_object(request, pk)

        if not (request.user.is_superuser or getattr(request.user, 'is_platform_staff', False)):
            membership = getattr(request, 'membership', None)
            if not membership or not (membership.is_admin or membership.has_permission('courses.delete')):
                return Response({'error': 'Permission denied.'}, status=status.HTTP_403_FORBIDDEN)

        course.status = AcademicStatus.ARCHIVED
        course.save(update_fields=['status'])
        return Response({'message': f"Course '{course.title}' archived successfully."})


class FacultyCoursePublishView(views.APIView):
    """
    Publish or unpublish a course.
    """
    permission_classes = [IsTenantMember]

    def post(self, request, pk):
        tenant = getattr(request, 'tenant', None)
        course = get_object_or_404(Course.objects.for_tenant(tenant), pk=pk)

        if not (request.user.is_superuser or getattr(request.user, 'is_platform_staff', False)):
            membership = getattr(request, 'membership', None)
            if not membership or not (membership.is_admin or membership.has_permission('courses.publish')):
                return Response({'error': 'Permission denied.'}, status=status.HTTP_403_FORBIDDEN)

        course.status = AcademicStatus.PUBLISHED if course.status != AcademicStatus.PUBLISHED else AcademicStatus.DRAFT
        course.save(update_fields=['status'])

        return Response({
            'message': f"Course status updated to '{course.status}'.",
            'status': course.status
        })


class FacultyModuleCreateView(views.APIView):
    """
    Add a new module to a course.
    """
    permission_classes = [IsTenantMember]

    def post(self, request, pk):
        tenant = getattr(request, 'tenant', None)
        course = get_object_or_404(Course.objects.for_tenant(tenant), pk=pk)

        title = request.data.get('title')
        description = request.data.get('description', '')
        order = request.data.get('order', course.modules.count() + 1)

        if not title:
            return Response({'error': 'Title is required.'}, status=status.HTTP_400_BAD_REQUEST)

        module = Module.objects.create(
            tenant=tenant,
            course=course,
            title=title,
            description=description,
            order=order
        )

        return Response(ModuleSerializer(module).data, status=status.HTTP_201_CREATED)


class FacultyLessonCreateView(views.APIView):
    """
    Add a lesson to a course module.
    """
    permission_classes = [IsTenantMember]

    def post(self, request, module_id):
        tenant = getattr(request, 'tenant', None)
        module = get_object_or_404(Module.objects.for_tenant(tenant), pk=module_id)

        title = request.data.get('title')
        lesson_type = request.data.get('lesson_type', 'article')
        content = request.data.get('content', '')
        duration_minutes = request.data.get('duration_minutes', 15)
        order = request.data.get('order', module.lessons.count() + 1)
        is_preview = request.data.get('is_preview', False)

        if not title:
            return Response({'error': 'Title is required.'}, status=status.HTTP_400_BAD_REQUEST)

        lesson = Lesson.objects.create(
            tenant=tenant,
            module=module,
            title=title,
            lesson_type=lesson_type,
            content=content,
            duration_minutes=duration_minutes,
            order=order,
            is_preview=is_preview
        )

        return Response(LessonSerializer(lesson).data, status=status.HTTP_201_CREATED)


class FacultyCohortCreateView(views.APIView):
    """
    Schedule an intake cohort for a course.
    """
    permission_classes = [IsTenantMember]

    def post(self, request, pk):
        tenant = getattr(request, 'tenant', None)
        course = get_object_or_404(Course.objects.for_tenant(tenant), pk=pk)

        serializer = CourseOfferingSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        cohort = serializer.save(tenant=tenant, course=course)

        return Response(CourseOfferingSerializer(cohort).data, status=status.HTTP_201_CREATED)
