# -*- coding: utf-8 -*-
import json

from django.contrib.auth.models import User
from django.test import Client
from rest_framework import status


class JsonTestClient(Client):
    """
    Represents a Client that in addition to the default response from the CRUD
    methods also returns the response content converted to a json object.
    """
    def __init__(self, *attrs, **kwargs):
        super(JsonTestClient, self).__init__(*attrs, **kwargs)
        self.ok_codes = [status.HTTP_200_OK, status.HTTP_201_CREATED]

    def get(self, *attrs, **kwargs):
        return self.__to_json(
            super(JsonTestClient, self).get(*attrs, **kwargs))

    def post(self, *attrs, **kwargs):
        return self.__to_json(
            super(JsonTestClient, self).post(*attrs, **kwargs))

    def put(self, *attrs, **kwargs):
        return self.__to_json(
            super(JsonTestClient, self).put(*attrs, **kwargs))

    def patch(self, *attrs, **kwargs):
        return self.__to_json(
            super(JsonTestClient, self).patch(*attrs, **kwargs))

    def __to_json(self, response):
        try:
            content = json.loads(response.content)
        except ValueError:
            content = None

        return response, content


class AuthenticatedTestClient(Client):
    """
    Represents a Client with a logged in superuser.
    """
    def __init__(self, *attrs, **kwargs):
        super(AuthenticatedTestClient, self).__init__(*attrs, **kwargs)
        admin_set = User.objects.filter(username='admin')
        if admin_set.count() > 0:
            # There is already an admin present so don't create a new one.
            self.user = admin_set.first()
        else:
            self.user = User.objects.create_superuser(
                'admin', 'admin@kamaji.io', 'admin')
        self.login(username='admin', password='admin')


class AuthenticatedJsonTestClient(JsonTestClient, AuthenticatedTestClient):
    """
    Represents a TestClient with an authenticated user. The test client
    behaves like a JsonTestClient in that it also returns the response content
    converted to a json object.
    :note: Can't get the extra arg (follow=True) to the request methods to work
    with this class, seems to be a problem with the multiple inheritance, use
    the simpler AuthenticatedTestClient instead if you need extra args.
    """
    def __init__(self, *attrs, **kwargs):
        super(AuthenticatedJsonTestClient, self).__init__(*attrs, **kwargs)
