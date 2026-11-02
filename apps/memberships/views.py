from rest_framework import views, status, generics
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.shortcuts import get_object_or_404
from django.db import transaction, models
from django.contrib.auth import get_user_model
from apps.tenants.models import Tenant
from common.permissions import IsTenantMember, IsTenantAdmin, HasTenantPermission
from .models import (
    TenantMembership,
    MembershipRole,
    Role,
    StaffInvitation,
    MembershipStatus,
    InvitationStatus,
)
from .serializers import (
    TenantMembershipSerializer,
    UpdateMembershipSerializer,
    StaffInvitationSerializer,
    CreateStaffInvitationSerializer,
    AcceptInvitationSerializer,
    RoleSerializer,
)

User = get_user_model()


class MemberListView(generics.ListAPIView):
    """
    List all members within the resolved tenant.
    Supports filtering by ?role=slug and searching by ?search=term.
    """
    serializer_class = TenantMembershipSerializer
    permission_classes = [IsTenantMember]

    def get_queryset(self):
        tenant = getattr(self.request, 'tenant', None)
        if not tenant:
            return TenantMembership.objects.none()

        qs = TenantMembership.objects.for_tenant(tenant)\
            .select_related('user', 'tenant')\
            .prefetch_related('roles')\
            .order_by('-joined_at')

        status_param = self.request.query_params.get('status')
        if status_param:
            qs = qs.filter(status=status_param)

        role_slug = self.request.query_params.get('role')
        if role_slug:
            qs = qs.filter(roles__slug=role_slug)

        search = self.request.query_params.get('search')
        if search:
            qs = qs.filter(
                models.Q(user__email__icontains=search) |
                models.Q(user__first_name__icontains=search) |
                models.Q(user__last_name__icontains=search)
            )

        return qs


class MemberDetailView(views.APIView):
    """
    Retrieve, update roles, or remove an institutional member.
    """
    permission_classes = [IsTenantAdmin]

    def get_object(self, pk):
        tenant = getattr(self.request, 'tenant', None)
        return get_object_or_404(
            TenantMembership.objects.for_tenant(tenant).select_related('user', 'tenant').prefetch_related('roles'),
            pk=pk
        )

    def get(self, request, pk):
        membership = self.get_object(pk)
        return Response(TenantMembershipSerializer(membership).data)

    def patch(self, request, pk):
        membership = self.get_object(pk)
        serializer = UpdateMembershipSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data

        with transaction.atomic():
            if 'status' in data:
                membership.status = data['status']
                membership.save(update_fields=['status', 'updated_at'])

            if 'role_slugs' in data:
                target_roles = Role.objects.filter(slug__in=data['role_slugs'])
                # Replace existing roles
                MembershipRole.objects.filter(membership=membership).delete()
                MembershipRole.objects.bulk_create([
                    MembershipRole(membership=membership, role=role)
                    for role in target_roles
                ])

        membership.refresh_from_db()
        return Response(TenantMembershipSerializer(membership).data)

    def delete(self, request, pk):
        membership = self.get_object(pk)
        # Soft delete by marking removed
        membership.status = MembershipStatus.REMOVED
        membership.save(update_fields=['status', 'updated_at'])
        return Response(
            {'message': f"Member {membership.user.email} removed from {membership.tenant.name}."},
            status=status.HTTP_200_OK
        )


class MemberSuspendView(views.APIView):
    """
    Suspend a member's access to the current tenant.
    """
    permission_classes = [IsTenantAdmin]

    def post(self, request, pk):
        tenant = getattr(request, 'tenant', None)
        membership = get_object_or_404(TenantMembership.objects.for_tenant(tenant), pk=pk)
        membership.status = MembershipStatus.SUSPENDED
        membership.save(update_fields=['status', 'updated_at'])
        return Response({
            'message': f"Member {membership.user.email} has been suspended.",
            'status': membership.status
        })


class MemberReactivateView(views.APIView):
    """
    Reactivate a suspended member in the current tenant.
    """
    permission_classes = [IsTenantAdmin]

    def post(self, request, pk):
        tenant = getattr(request, 'tenant', None)
        membership = get_object_or_404(TenantMembership.objects.for_tenant(tenant), pk=pk)
        membership.status = MembershipStatus.ACTIVE
        membership.save(update_fields=['status', 'updated_at'])
        return Response({
            'message': f"Member {membership.user.email} has been reactivated.",
            'status': membership.status
        })


class StaffInvitationListView(views.APIView):
    """
    List invitations or send a new invitation.
    """
    permission_classes = [IsTenantAdmin]

    def get(self, request):
        tenant = getattr(request, 'tenant', None)
        if not tenant:
            return Response([])

        invitations = StaffInvitation.objects.for_tenant(tenant)\
            .select_related('role', 'invited_by')\
            .order_by('-created_at')

        return Response(StaffInvitationSerializer(invitations, many=True).data)

    def post(self, request):
        tenant = getattr(request, 'tenant', None)
        if not tenant:
            return Response({'error': 'No active institution found.'}, status=status.HTTP_400_BAD_REQUEST)

        serializer = CreateStaffInvitationSerializer(data=request.data, context={'tenant': tenant})
        serializer.is_valid(raise_exception=True)

        email = serializer.validated_data['email'].lower()
        role_slug = serializer.validated_data['role_slug']
        role = Role.objects.get(slug=role_slug)

        invitation = StaffInvitation.objects.create(
            tenant=tenant,
            email=email,
            role=role,
            invited_by=request.user
        )

        return Response(
            StaffInvitationSerializer(invitation).data,
            status=status.HTTP_201_CREATED
        )


class StaffInvitationRevokeView(views.APIView):
    """
    Revoke a pending staff invitation.
    """
    permission_classes = [IsTenantAdmin]

    def post(self, request, pk):
        tenant = getattr(request, 'tenant', None)
        invitation = get_object_or_404(StaffInvitation.objects.for_tenant(tenant), pk=pk)

        if invitation.status != InvitationStatus.PENDING:
            return Response(
                {'error': f"Cannot revoke invitation with status '{invitation.status}'."},
                status=status.HTTP_400_BAD_REQUEST
            )

        invitation.status = InvitationStatus.REVOKED
        invitation.save(update_fields=['status'])
        return Response({'message': f"Invitation for {invitation.email} has been revoked."})


class AcceptInvitationView(views.APIView):
    """
    Accept an invitation token.
    Public endpoint: allows new users to register and join,
    or existing logged-in users to accept into their account.
    """
    permission_classes = [AllowAny]

    def post(self, request, token):
        invitation = get_object_or_404(StaffInvitation, token=token)

        if not invitation.is_valid:
            return Response(
                {'error': 'This invitation token has expired or has already been used.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        user = request.user if request.user and request.user.is_authenticated else None

        if not user:
            # Check if an account already exists with this email
            user = User.objects.filter(email__iexact=invitation.email).first()

            if not user:
                # Require password for new user account
                serializer = AcceptInvitationSerializer(data={'token': token, **request.data})
                serializer.is_valid(raise_exception=True)
                password = serializer.validated_data.get('password')
                if not password:
                    return Response(
                        {'error': 'A password is required to create your account.'},
                        status=status.HTTP_400_BAD_REQUEST
                    )

                user = User.objects.create_user(
                    email=invitation.email,
                    password=password,
                    first_name=serializer.validated_data.get('first_name', ''),
                    last_name=serializer.validated_data.get('last_name', ''),
                    email_verified=True
                )

        membership = invitation.accept(user)

        return Response({
            'message': f"Successfully joined {invitation.tenant.name}.",
            'tenant': {
                'id': str(invitation.tenant.id),
                'name': invitation.tenant.name,
                'slug': invitation.tenant.slug,
            },
            'membership_id': str(membership.id),
            'role': invitation.role.name,
        }, status=status.HTTP_200_OK)


class RoleListView(views.APIView):
    """
    List available institutional roles for role assignment.
    """
    permission_classes = [IsTenantAdmin]

    def get(self, request):
        roles = Role.objects.filter(is_platform_role=False).prefetch_related('permissions')
        return Response(RoleSerializer(roles, many=True).data)
