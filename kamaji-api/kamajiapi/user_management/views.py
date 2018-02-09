# -*- coding: utf-8 -*-
from collections import OrderedDict

from django.contrib.auth.models import User
from django.http import Http404
from rest_framework import permissions, status
from rest_framework.exceptions import NotFound
from rest_framework.generics import (
    ListCreateAPIView, RetrieveUpdateDestroyAPIView, RetrieveAPIView,
    ListAPIView
)
from rest_framework.response import Response
from rest_framework.reverse import reverse
from rest_framework.views import APIView

from shared.urlresolvers import get_uri_template
from shared.views import LookupMixin
from user_management.models import (
    GlobalGroup, Project, ProjectGroup, KamajiUser,
)
from user_management.permissions import (
    UserSinglePermission, IsAuthenticatedOrOptions
)
from user_management.project_extractor import ProjectExtractor
from user_management.serializers import (
    GlobalGroupSerializer, ProjectGroupSerializer, ProjectSerializer,
    UserSerializer, ProjectMembershipSerializer, PasswordChangeSerializer,
    PasswordChangeTokenSerializer
)


class UserManagementLinksList(RetrieveAPIView):
    """
    List all available endpoints under user_management.
    """
    def get(self, request, *args):
        return Response(OrderedDict(
            [('global_groups_link', reverse('global_groups', request=request)),
             ('project_groups_link', reverse('project_groups', request=request)),
             ('projects_link', reverse('projects', request=request)),
             ('users_link', reverse('users', request=request))]
        ))


class PasswordLinksList(APIView):
    """
    The available endpoints managing password change
    """
    permission_classes = (
        permissions.AllowAny,
    )

    def get(self, request, *args):
        return Response(OrderedDict((
            ('password_reset_token_request_link_template', get_uri_template(
                'password-reset-token-request',
                request,
                'email'
            )),
            ('password_reset_token_validate_link_template', get_uri_template(
                'password-reset-token-validate',
                request,
                'email'
            )),
            ('password_change_link_template', get_uri_template(
                'password-change',
                request,
                'email'
            ))
        )))


class ProjectGroupList(ListCreateAPIView):
    """
    List or create groups tied to a project and role.
    Membership in a project group allows users to reach project specific
    endpoints with info only relevant for the project of their group.
    """
    queryset = ProjectGroup.objects.all()
    serializer_class = ProjectGroupSerializer


class ProjectGroupSingle(RetrieveUpdateDestroyAPIView, ProjectExtractor):
    """
    Delete, update or show info about a single project group. This endpoints
    assigns membership to project groups.
    """
    queryset = ProjectGroup.objects.all()
    serializer_class = ProjectGroupSerializer
    lookup_field = 'id'

    def extract_project(self, request):
        group_id = request.parser_context['kwargs']['id']
        try:
            return ProjectGroup.objects.get(id=group_id).project
        except:
            raise Http404


class ProjectGroupsPerProject(ListAPIView):
    """
    List all project groups associated with a specified group.
    """
    serializer_class = ProjectGroupSerializer
    lookup_url_kwarg = 'project'

    def get_queryset(self):
        return ProjectGroup.objects.filter(**self.kwargs)


class GlobalGroupList(ListCreateAPIView):
    """
    List or create groups with global access tied to a role.
    Membership in a global group allows users to access endpoints not
    specifically tied to a project but that effect the whole environment.
    """
    queryset = GlobalGroup.objects.all()
    serializer_class = GlobalGroupSerializer


class GlobalGroupSingle(RetrieveUpdateDestroyAPIView):
    """
    Lookup a specific global group.
    Delete, update or show info about a single global group. This endpoint
    assigns membership to global groups.
    """
    queryset = GlobalGroup.objects.all()
    serializer_class = GlobalGroupSerializer
    lookup_field = 'id'


class ProjectList(ListCreateAPIView):
    """
    List or create projects.
    A project can be assigned to a project group to allow users access to
    project specific endpoints.
    """
    queryset = Project.objects.all()
    serializer_class = ProjectSerializer


class ProjectSingle(RetrieveUpdateDestroyAPIView):
    """
    Show info about a single project.
    """
    queryset = Project.objects.all()
    serializer_class = ProjectSerializer
    lookup_url_kwarg = 'project'


class UserList(ListCreateAPIView):
    """
    List or create users.
    A user can be assigned to a group to allow access to endpoints.
    """
    queryset = User.objects.filter(kamajiuser__isnull=False)
    serializer_class = UserSerializer


class UserSingle(RetrieveUpdateDestroyAPIView):
    """
    Delete, update or show info about a single user.
    """
    queryset = User.objects.filter(kamajiuser__isnull=False)
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticatedOrOptions, UserSinglePermission]
    lookup_url_kwarg = 'user_id'


class UsersByProjectList(ListAPIView):
    """
    List users that are connected to KamajiUsers and are either member of a
    ProjectGroup for this project or is granted access to this project by
    being a Global Administrator or Spectator.
    """
    serializer_class = UserSerializer

    def get_queryset(self):
        """
        :return: All users that has a kamajiuser and is a member of this project or a global project.
        """
        project = Project.objects.get(id=self.kwargs['project'])
        return project.members

    def get_serializer_context(self):
        context = super(UsersByProjectList, self).get_serializer_context()
        context['project'] = Project.objects.get(id=self.kwargs['project'])
        return context


class UsersByProjectSingle(RetrieveAPIView):
    """
    Show info about a single project user.
    """
    serializer_class = UserSerializer
    lookup_url_kwarg = 'user_id'
    permission_classes = [IsAuthenticatedOrOptions, UserSinglePermission]

    def get_queryset(self):
        """
        :return: All users that has a kamajiuser and is a member of this project or a global project.
        """
        project = Project.objects.get(id=self.kwargs['project'])
        return project.members

    def get_serializer_context(self):
        context = super(UsersByProjectSingle, self).get_serializer_context()
        context['project'] = Project.objects.get(id=self.kwargs['project'])
        return context


class ProjectMembership(APIView):
    """
    View to add a user to a project with a specific role.
    """

    def get_serializer(self, *args, **kwargs):
        return ProjectMembershipSerializer(*args, **kwargs)

    @property
    def user(self):
        try:
            return User.objects.get(username=self.kwargs['username'])
        except User.DoesNotExist:
            raise NotFound("User '{0}' does not exist.".format(
                self.kwargs['username']
            ))

    def put(self, *args, **kwargs):
        serializer = self.get_serializer(data=self.request.data)
        serializer.is_valid(raise_exception=True)

        self.user.kamajiuser.set_project_role(
            self.kwargs['project_id'],
            serializer.validated_data['role']
        )
        return Response(status=status.HTTP_204_NO_CONTENT)

    def delete(self, *args, **kwargs):
        self.user.kamajiuser.set_project_role(self.kwargs['project_id'], None)
        return Response(status=status.HTTP_204_NO_CONTENT)


class RequestPasswordChangeTokenView(APIView):
    """
    To request a password reset, simply perform a post request. No body
    necessary.
    """
    # Requesting a password reset needs to be allowed without logging in
    permission_classes = (
        permissions.AllowAny,
    )

    def get_user(self):
        return KamajiUser.objects.get(user__email=self.kwargs['email'])

    def post(self, request, **kwargs):
        try:
            u = self.get_user()
            u.send_password_reset_email('{0}://{1}'.format(
                request.scheme,
                request.get_host()
            ))
        except KamajiUser.DoesNotExist:
            # In case the email address does not match any users, do nothing
            # to not allow for users to brute force for valid email addresses
            pass

        return Response(status=status.HTTP_204_NO_CONTENT)


class PasswordResetTokenValidationView(LookupMixin, APIView):
    """
    Validate a password reset token for a user. To perform token validation,
    POST a JSON object with token in a field named token.
    """
    permission_classes = (
        permissions.AllowAny,
    )

    queryset = User.objects.all()
    lookup_field = 'email'

    def get_serializer(self, *args, **kwargs):
        return PasswordChangeTokenSerializer(*args, **kwargs)

    def _get_validated_data(self):
        try:
            user = self.get_object()
        except User.DoesNotExist:
            user = None

        serializer = self.get_serializer(
            data=self.request.data,
            user=user
        )

        serializer.is_valid(raise_exception=True)

        return user, serializer.validated_data

    def post(self, request, *args, **kwargs):
        self._get_validated_data()

        return Response(status=status.HTTP_204_NO_CONTENT)


class PasswordChange(PasswordResetTokenValidationView):
    """
    To change the password for a user, perform a post request containing a
    valid password reset token (token) and the requested new password
    (new password).
    """
    def get_serializer(self, *args, **kwargs):
        return PasswordChangeSerializer(*args, **kwargs)

    def post(self, request, *args, **kwargs):
        user, data = self._get_validated_data()

        user.set_password(data['new_password'])
        user.save()

        return Response(status=status.HTTP_204_NO_CONTENT)
