# -*- coding: utf-8 -*-
import logging
from itertools import chain

from django.conf import settings
from rest_framework import permissions

from user_management.models import GlobalGroup, ProjectGroup

logger = logging.getLogger(__name__)


class HasGroupAccessOrOptions(permissions.BasePermission):
    def has_permission(self, request, view):
        """
        Checks for group access to the specified view for the current
        user in both global and project groups.

        :param request: The incoming request.
        :type: request: HttpRequest
        :param view: The view that is to be accessed.
        :return: True if user has access to the specified view,
                 False otherwise.
        """
        if request.method == 'OPTIONS':
            return True

        view_name = view.__class__.__name__

        global_groups = GlobalGroup.objects.filter(users=request.user.id)

        project_groups = []
        project = HasGroupAccessOrOptions.parse_project(request, view)
        if project is not None:
            project_groups = ProjectGroup.objects.filter(project_id=project,
                                                         users=request.user)

        for group in chain(global_groups, project_groups):
            if group.permits_view(view_name, request.method):
                return True

        if settings.DEBUG:
            request.debug_permission_overridden = True

            logger.warning(
                'Allowing debug access for user "%s" (%i). This request '
                'would have been denied if the API was in production mode',
                request.user.username,
                request.user.id
            )

            return True

        logger.info("Denying access for user with id '%i', "
                    "requesting permission %s for view %s.", request.user.id,
                    request.method, view_name)

        return False

    @staticmethod
    def parse_project(request, view):
        """
        Finds and returns the project id of the project associated with
        the current request by first asking the view to parse it for us,
        then looking in the data object or the kwargs of the request.

        :param request: The current 'HttpRequest' object
        :return: Project id of the project associated with the request
                 else None
        """
        try:
            return view.extract_project(request)
        except AttributeError:
            pass

        try:
            return request.data.project
        except AttributeError:
            pass

        try:
            return request.parser_context['kwargs']['project']
        except (AttributeError, KeyError):
            pass

        try:
            return request.parser_context['kwargs']['project_id']
        except (AttributeError, KeyError):
            return None


class UserSinglePermission(permissions.BasePermission):
    def has_permission(self, request, view):
        """
        Denies requests that tries to delete the same user that is
        authenticated.

        :param request: The incoming request.
        :type request: HttpRequest
        :param view: The view that is to be accessed.
        :type view: APIView
        :return: False if the user is trying to delete itself, True otherwise.
        :rtype: bool
        """
        if request.method == 'DELETE':
            if UserSinglePermission.parse_user(request) == request.user.id:
                logger.info("Denying access for user with id '%i'.",
                            request.user.id)
                return False
        elif request.method in ('PUT', 'PATCH') + permissions.SAFE_METHODS:
            if UserSinglePermission.parse_user(request) == request.user.id:
                return True
        return HasGroupAccessOrOptions().has_permission(request, view)

    @staticmethod
    def parse_user(request):
        """
        Parses the user_id from the kwargs dict of the request.

        :param request: The incoming request.
        :type request: HttpRequest
        :return: None if the user_id is not specified in the kwargs dict,
        the user_id otherwise
        :raises: KeyError: if the user_id is missing from the kwargs dict.
        :rtype: int
        """
        try:
            return int(request.parser_context['kwargs']['user_id'])
        except KeyError:
            return None


class IsAuthenticatedOrOptions(permissions.BasePermission):
    def has_permission(self, request, view):
        """
        Allows all OPTIONS requests.

        :param request: The incoming request.
        :type request: HttpRequest
        :param view: The view that is to be accessed.
        :type view: APIView
        :return: True if the request method is OPTIONS, false otherwise.
        :rtype: bool
        """
        if request.method == 'OPTIONS':
            return True
        else:
            return request.user.is_authenticated()


def jwt_response_payload_handler(token, user=None, request=None):
    """
    This function generates the output returned when a user has successfully
    obtained a new token.

    :param token: The generated token
    :type token: str
    :param user: The object representing the user that has obtained the token
    :type user: User
    :param request: The incoming request
    :type request: HttpRequest
    :return: A dictionary with the token and the permissions the user has
    :rtype: dict
    """
    global_permissions = []
    for group in user.globalgroups.all():
        for permission in group.role.permissions.all():
            global_permissions.append(permission.name)

    return {
        'token': token,
        'global_permissions': global_permissions
    }