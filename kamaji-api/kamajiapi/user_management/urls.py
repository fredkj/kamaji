# -*- coding: utf-8 -*-
from django.conf.urls import url

from shared.views import ReducedKwargsRedirectView
from user_management.views import (
    ProjectGroupList, ProjectGroupSingle, ProjectSingle, ProjectList,
    GlobalGroupList, GlobalGroupSingle, UserList, UserSingle,
    UserManagementLinksList, ProjectGroupsPerProject,
    UsersByProjectList, UsersByProjectSingle, ProjectMembership,
    RequestPasswordChangeTokenView, PasswordResetTokenValidationView, PasswordChange,
    PasswordLinksList
)

urlpatterns = [
    url(r'^user_management/$',
        UserManagementLinksList.as_view(),
        name='user_management-root'
    ),
    url(r'^user_management/groups/project/(?P<id>\d+)/$',
        ProjectGroupSingle.as_view(),
        name='project_groups_single'
    ),
    url(r'^user_management/groups/project/$',
        ProjectGroupList.as_view(),
        name='project_groups'
    ),
    url(r'^user_management/groups/global/(?P<id>\d+)/$',
        GlobalGroupSingle.as_view(),
        name='global_groups_single'
    ),
    url(r'^user_management/groups/global/$',
        GlobalGroupList.as_view(),
        name='global_groups'
    ),
    url(r'^projects/(?P<project_id>\d+)/memberships/(?P<username>[-\w]+)/$',
        ProjectMembership.as_view(),
        name='project_memberships'
        ),
    url(r'^projects/(?P<project>\d+)/$',
        ProjectSingle.as_view(),
        name='project_single'
    ),
    url(r'^projects/$',
        ProjectList.as_view(),
        name='projects'
    ),
    url(r'projects/(?P<project>\d+)/users/$',
        UsersByProjectList.as_view(),
        name='users_per_project'
    ),
    url(r'projects/(?P<project>\d+)/users/(?P<user_id>\d+)/$',
        UsersByProjectSingle.as_view(),
        name='user_per_project'
    ),
    url(r'projects/(?P<project>\d+)/groups/$',
        ProjectGroupsPerProject.as_view(),
        name='projectgroup_per_project'
    ),
    url(r'projects/(?P<project>\d+)/groups/(?P<id>\d+)/$',
        ReducedKwargsRedirectView.as_view(
            pattern_name='project_groups_single',
            permanent=True,
            use_kwargs=('id', )
        )
    ),
    url(r'^user_management/users/(?P<user_id>\d+)/$',
        UserSingle.as_view(),
        name='user_single'
    ),
    url(r'^user_management/users/$',
        UserList.as_view(),
        name='users'
    ),
    url(
        r'^auth/password/change_token_request/(?P<email>.+)$',
        RequestPasswordChangeTokenView.as_view(),
        name='password-reset-token-request'
    ),
    url(
        r'^auth/password/change_token_validate/(?P<email>.+)$',
        PasswordResetTokenValidationView.as_view(),
        name='password-reset-token-validate'
    ),
    url(
        r'^auth/password/password_change/(?P<email>.+)',
        PasswordChange.as_view(),
        name='password-change'
    ),
    url(
        r'^auth/password/$',
        PasswordLinksList.as_view(),
        name='password-root'
    ),
]
