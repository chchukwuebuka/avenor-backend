from django.urls import path
from .views import (
    MemberListView,
    MemberDetailView,
    MemberSuspendView,
    MemberReactivateView,
    StaffInvitationListView,
    StaffInvitationRevokeView,
    AcceptInvitationView,
    RoleListView,
)

urlpatterns = [
    # Members Management
    path('', MemberListView.as_view(), name='member-list'),
    path('roles/', RoleListView.as_view(), name='role-list'),
    path('<uuid:pk>/', MemberDetailView.as_view(), name='member-detail'),
    path('<uuid:pk>/suspend/', MemberSuspendView.as_view(), name='member-suspend'),
    path('<uuid:pk>/reactivate/', MemberReactivateView.as_view(), name='member-reactivate'),

    # Invitations
    path('invitations/', StaffInvitationListView.as_view(), name='invitation-list-create'),
    path('invitations/<uuid:pk>/revoke/', StaffInvitationRevokeView.as_view(), name='invitation-revoke'),
    path('invitations/<str:token>/accept/', AcceptInvitationView.as_view(), name='invitation-accept'),
]
