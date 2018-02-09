# -*- coding: utf-8 -*-
from collections import OrderedDict

from rest_framework import permissions

import api
from fabric.models import Setting
from rest_framework.response import Response
from rest_framework.reverse import reverse
from rest_framework.views import APIView


class APIRootLinksList(APIView):
    """ Available root endpoints """

    # Allow everyone as this endpoint is sometimes called by the loadbalancer
    # for a brief status check of the api.
    permission_classes = (
        permissions.AllowAny,
    )

    def get(self, request, *args):
        return Response({
            'auth_link': reverse('auth-root', request=request),
            'fabric_link': reverse('fabric-root', request=request),
            'projects_link': reverse('projects', request=request),
            'user_management_link': reverse('user_management-root', request=request),
            'status_link': reverse('status', request=request)
        })


class AuthLinksList(APIView):
    """ Available endpoints under /auth/ """
    permission_classes = (
        # Since all endpoints in this menu are available for unauthorized users
        # we'll add anyone in to view the menu
        permissions.AllowAny,
    )

    def get(self, request, *args):
        return Response(OrderedDict([
            ('token_link', reverse('token', request=request)),
            ('token_refresh_link', reverse('token-refresh', request=request)),
            ('password_link', reverse('password-root', request=request))
        ]))


class StatusView(APIView):
    """
    Endpoint used by load balancer/monitoring software to check
    that the API is alive and can connect to the database
    """

    # Allow everyone as this endpoint is sometimes called by the loadbalancer
    # for a brief status check of the api.
    permission_classes = (
        permissions.AllowAny,
    )

    def get(self, request, *args, **kwargs):
        try:
            Setting.objects.get(setting="DomainSetting")
        except Exception:
            return Response(status=500)

        if hasattr(api, '__commit__'):
            version = '{0} ({1})'.format(api.__version__, api.__commit__)
        else:
            version = api.__version__

        status_data = {
            'api-version': version
        }

        return Response(status_data)
