# -*- coding: utf-8 -*-
import json
import os
import uuid

import mock
from django.conf import settings
from django.contrib.auth.models import User
from django.core.urlresolvers import RegexURLResolver, RegexURLPattern
from django.test import Client, TestCase, RequestFactory
from django.views.generic import RedirectView
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny

from api.celery import app
from fabric.models import Setting, Host, Credential
from shared.testclient import AuthenticatedJsonTestClient
from user_management import permissions
from user_management.models import (
    Role, Project, ProjectGroup, GlobalGroup, Permission,
    ViewPermission
)
from user_management.permissions import UserSinglePermission


class PermissionTestCase(TestCase):
    """
    TestCase to test the permission classes 'HasGlobalAccess'
    and 'HasProjectAccess'.
    """
    roles = {
        'superuser': {
            ('Test1', 'TestView1'): [True, True, True, True],
            ('Test2', 'TestView2'): [True, True, True, True]
        },
        'spectator': {
            ('Test1', 'TestView1'): [False, True, False, False]
        }
    }

    request_factory = RequestFactory()
    permission_handler = permissions.HasGroupAccessOrOptions()

    all_methods = [request_factory.post, request_factory.delete,
                   request_factory.put, request_factory.get,
                   request_factory.head, request_factory.options,
                   request_factory.patch]

    def setUp(self):
        settings.CELERY_ALWAYS_EAGER = True
        settings.BROKER_BACKEND = 'memory'
        app.CELERY_ALWAYS_EAGER = True

        self.populate_roles()
        self.populate_groups()

    def populate_roles(self):
        """
        Populates the Action, Permission and Roles tables according to the
        roles dictionary.
        """

        test1manage = Permission.create(
            name='test1:manage',
            views=[
                {
                    'view_name': 'TestView1',
                    'create': True,
                    'read': True,
                    'update': True,
                    'delete': True
                }
            ]
        )

        test2manage = Permission.create(
            name='test2:manage',
            views=[
                {
                    'view_name': 'TestView2',
                    'create': True,
                    'read': True,
                    'update': True,
                    'delete': True
                }
            ]
        )

        test1read = Permission.create(
            name='test1:read',
            views=[
                {
                    'view_name': 'TestView1',
                    'read': True,
                }
            ]
        )

        global_superuser = Role.objects.get(name='global_administrator')

        global_superuser.permissions.add(test1manage)
        global_superuser.permissions.add(test2manage)

        global_spectator = Role.objects.get(name='global_spectator')
        global_spectator.permissions.add(test1read)

    @mock.patch('user_management.models.Project.instances')
    @mock.patch('fabric.models.Instance.add_users')
    @mock.patch('shared.openstack2.shortcuts.OSResourceShortcut.get')
    @mock.patch('shared.openstack2.sessions.OSSession._OSSession__request')
    @mock.patch('user_management.models.Project.dns_zone')
    def populate_groups(
            self,
            dns_zone_mock,
            request_mock,
            shortcut_mock,
            add_users_mock,
            instance_mock
    ):
        """
        Populates the database with users in the different groups
        'global spectators', 'global superusers', 'project spectators'
        and 'project superusers'.
        """
        request_mock.return_value.json = lambda: {
            'project': {
                'id': uuid.uuid1(),
                'enabled': True,
                'description': 'test',
                'name': 'test',
                'domain_id': 'test',
            }
        }

        shortcut_mock.return_value = {'id': '123'}
        instance_mock.return_value = []

        self.spectator_role = Role.objects.get(name='global_spectator')
        self.administrator_role = Role.objects.get(name='global_administrator')

        Setting.objects.create(
            setting='DomainSetting',
            value={'domain': 'customer.kamaji.customer.tld'}
        )

        Host.objects.create(type='vip', ip_address='10.0.0.1')
        Credential.objects.create(
            service=Credential.POWERDNS_API_KEY,
            password='asd',
            username='asd'
        )

        self.project = Project.objects.create(
            name='test project 1',
            description='test project 1 description',
            enabled=True
        )

        self.other_project = Project.objects.create(
            name='test project 2',
            description='test project 2 description',
            enabled=False
        )

        self.project_spectators = ProjectGroup(
            project=self.project,
            role=self.spectator_role
        )

        self.project_spectators.save()

        self.project_superusers = ProjectGroup(
            project=self.project,
            role=self.administrator_role
        )

        self.project_superusers.save()

        self.global_spectators, _ = GlobalGroup.objects.get_or_create(
            name='Global Spectators', role=self.spectator_role)
        self.global_superusers, _ = GlobalGroup.objects.get_or_create(
            name='Global Superusers', role=self.administrator_role)

        self.project_superuser = User.objects.create_user(
            username='project_superuser',
            email='alfons@pwny.se',
            password='qwe123'
        )
        self.project_superuser.unhashed_password = 'qwe123'

        self.global_spectator = User.objects.create_user(
            username='global_spectator',
            email='morgan@pwny.se',
            password='qwe123'
        )

        self.global_spectator.unhashed_password = 'qwe123'
        self.project_spectator = User.objects.create_user(
            username='project_spectator',
            email='connor@pwny.se',
            password='qwe123'
        )
        self.project_spectator.unhashed_password = 'qwe123'

        self.global_superuser = User.objects.create_user(
            username='global_superuser',
            email='t1000@pwny.se',
            password='qwe123'
        )
        self.global_superuser.unhashed_password = 'qwe123'

        self.global_spectators.users.add(self.global_spectator)
        self.global_superusers.users.add(self.global_superuser)

        self.project_spectators.users.add(self.project_spectator)
        self.project_superusers.users.add(self.project_superuser)

    def test_global_spectators_can_only_get(self):
        allowed_methods = [self.request_factory.get, self.request_factory.head,
                           self.request_factory.options]
        self.can_access_allowed_methods(self.global_spectator, TestView1(),
            self.permission_handler,
            allowed_methods)

    def test_global_superusers_can_do_everything(self):
        self.can_access_allowed_methods(self.global_superuser, TestView1(),
            self.permission_handler,
            self.all_methods)

    def test_project_spectators_can_only_get_inside_project(self):
        allowed_methods = [self.request_factory.get, self.request_factory.head,
                           self.request_factory.options]

        # Correct Project, View and ProjectHandler
        self.can_access_allowed_methods(self.project_spectator, TestView1(),
            self.permission_handler,
            allowed_methods, self.project.id)

        # Correct project on view not included in role
        self.can_access_allowed_methods(self.project_spectator, TestView2(),
            self.permission_handler,
            [self.request_factory.options],
            self.project.id)

        # View included in role but with a project the user is not working in
        self.can_access_allowed_methods(self.project_spectator, TestView1(),
            self.permission_handler,
            [self.request_factory.options],
            self.other_project.id)

        # Global handler with a user only associated with a ProjectGroup
        self.can_access_allowed_methods(self.project_spectator, TestView1(),
            self.permission_handler,
            [self.request_factory.options])

    def test_project_superusers_can_only_do_everything_inside_project(self):
        # Correct Project on ProjectHandler
        self.can_access_allowed_methods(self.project_superuser, TestView1(),
            self.permission_handler,
            self.all_methods, self.project.id)

        # Wrong Project
        self.can_access_allowed_methods(self.project_superuser, TestView1(),
            self.permission_handler,
            [self.request_factory.options],
            self.other_project.id)

    def test_user_parse(self):
        permission = UserSinglePermission()
        for http_method in self.all_methods:
            request = http_method('/test/')
            request.user = self.global_superuser
            request.parser_context = {
                'kwargs': {
                    'user_id': str(self.global_superuser.id)
                }
            }

            parsed_user_id = permission.parse_user(request)

            self.assertEquals(parsed_user_id, self.global_superuser.id)
            self.assertEquals(type(parsed_user_id), int)

        for http_method in self.all_methods:
            request = http_method('/test/')
            request.user = self.global_superuser
            request.parser_context = {}

            parsed_user_id = permission.parse_user(request)

            self.assertEquals(parsed_user_id, None)

    # region user crud test cases
    # region user creation test cases
    def test_user_creation_without_login(self):
        """
        Verify that an unauthenticated user is not allowed to create new users
        """
        http_client = Client()
        response = http_client.post('/user_management/users/', {
            'username': 'daniel',
            'password': 's3cr3t!'
        })

        self.assertEquals(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_user_creation_with_unauthorized_user(self):
        """
        Verify that a user without proper permissions is not allowed to create
        new users.
        """
        http_client = Client()
        http_client.login(username=self.global_spectator.username,
            password=self.global_spectator.unhashed_password)

        response = http_client.post('/user_management/users/', {
            'username': 'daniel',
            'password': 's3cr3t!'
        })

        self.assertEquals(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_user_creation_with_authorized_user(self):
        """
        Verify that a user with proper permissions is allowed to create a new
        user.
        """
        user_info = {
            'username': 'daniel',
            'password': 's3cr3t!',
            'first_name': 'Daniel',
            'last_name': 'Matsson',
            'email': 'daniel@kamaji.io'
        }

        http_client = Client()
        http_client.login(username=self.global_superuser.username,
            password=self.global_superuser.unhashed_password)

        response = http_client.post('/user_management/users/', user_info)

        self.assertEquals(response['Content-Type'], 'application/json')

        created_user = response.json()
        self.assertIn('id', created_user)
        self.assertIn('username', created_user)
        self.assertIn('first_name', created_user)
        self.assertIn('last_name', created_user)
        self.assertIn('last_login', created_user)
        self.assertIn('global_role', created_user)
        self.assertIn('project_roles', created_user)

        for user_property in user_info:
            if user_property == 'password':
                continue
            self.assertEquals(user_info[user_property],
                created_user[user_property])

        self.assertTrue(http_client.login(**user_info))

    # endregion

    # region user read test cases
    def test_get_users_without_login(self):
        """
        Verify that an unauthenticated user is not allowed to retrieve the
        global list of users.
        """
        api_client = Client()
        response = api_client.get('/user_management/users/')

        self.assertEquals(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_user_get_self(self):
        """
        Verify that a user is able to retrieve it's own user.
        """
        api_client = Client()
        api_client.login(username=self.global_spectator.username,
            password=self.global_spectator.unhashed_password)

        response = api_client.get('/user_management/users/{0}/'
            .format(self.global_spectator.id))

        user_payload = response.json()

        self.assertEquals(response.status_code, status.HTTP_200_OK)

        self.assertIn('id', user_payload)
        self.assertIn('username', user_payload)
        self.assertIn('first_name', user_payload)
        self.assertIn('last_name', user_payload)
        self.assertIn('last_login', user_payload)
        self.assertIn('project_roles', user_payload)

        self.assertEquals(user_payload['username'],
            self.global_spectator.username)

        self.assertEquals(user_payload['first_name'],
            self.global_spectator.first_name)

        self.assertEquals(user_payload['last_name'],
            self.global_spectator.last_name)

    def test_get_users_as_project_spectator(self):
        """
        Verify that a project spectator is not allowed to retrieve the global
        list of users.
        """
        api_client = Client()
        api_client.login(username=self.project_spectator.username,
            password=self.project_spectator.unhashed_password)

        response = api_client.get('/user_management/users/')

        self.assertEquals(response.status_code, status.HTTP_403_FORBIDDEN)

    @mock.patch('user_management.serializers.UserSerializer.to_representation')
    def test_get_users_as_global_spectator(self, to_representation_mock):

        """
        Verify that a global spectator is allowed to retrieve the global
        list of users.
        """
        to_representation_mock.return_value = {}
        api_client = Client()
        api_client.login(username=self.global_spectator.username,
            password=self.global_spectator.unhashed_password)

        response = api_client.get('/user_management/users/')

        self.assertEquals(response.status_code, status.HTTP_200_OK)

    @mock.patch('user_management.serializers.ProjectGroup')
    def test_user_get_in_other_projects(self, project_group_mock):
        """
        Verify that the a project spectator is not allowed to retrieve a user
        object.
        """
        api_client = Client()
        api_client.login(username=self.project_spectator.username,
            password=self.project_spectator.unhashed_password)

        response = api_client.get('/user_management/users/{0}/'
            .format(self.global_spectator.id))

        self.assertEquals(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_user_get_as_global_spectator(self):
        """
        Verify that a global spectator is allowed to retrieve a user object
        """
        api_client = Client()
        api_client.login(username=self.global_spectator.username,
            password=self.global_spectator.unhashed_password)

        response = api_client.get('/user_management/users/{0}/'
            .format(self.global_superuser.id))

        self.assertEquals(response.status_code, status.HTTP_200_OK)

    # endregion

    # region user update test cases
    @mock.patch('fabric.models.Instance.remove_users')
    def test_update_other_user_as_global_superuser(self, remote_users_mock):
        """
        Verify that a global super user is allowed to remove users.
        """
        victim1 = User.objects.create_user('victim1', password='victimpass')
        victim1.unhashed_password = 'victimpass'
        User.objects.create_user('victim2')
        User.objects.create_user('victim3')
        User.objects.create_user('victim4')
        User.objects.create_user('victim5')

        pre_user_count = len(User.objects.all())

        http_client = Client()

        # Verify that the newly created is able to login.
        self.assertTrue(http_client.login(username=victim1.username,
            password=victim1.unhashed_password))

        http_client.login(username=self.global_superuser.username,
            password=self.global_superuser.unhashed_password)
        response = http_client.delete('/user_management/users/{0}/'
            .format(victim1.id))

        post_user_count = len(User.objects.all())

        self.assertEquals(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEquals(len(User.objects.filter(id=victim1.id)), 0)
        self.assertEquals(pre_user_count, post_user_count + 1)

        # Verify that the victim can no longer login after removal
        self.assertFalse(http_client.login(username=victim1.username,
            password=victim1.unhashed_password))

    def test_user_update_self(self):
        """
        Verify that a non-admin user is allowed to update it's own user
        details, both through the PATCH and PUT methods.
        """
        api_client = Client()
        api_client.login(username=self.global_spectator.username,
            password=self.global_spectator.unhashed_password)

        # Begin verifying partial update using the PATCH method
        response = api_client.patch('/user_management/users/{0}/'
            .format(self.global_spectator.id),
            json.dumps({
                'first_name': 'global',
                'last_name': 'spectator'
            }), content_type='application/json')

        updated_user = response.json()

        self.assertEquals(response.status_code, status.HTTP_200_OK)
        self.assertEquals(updated_user['first_name'], 'global')
        self.assertEquals(updated_user['last_name'], 'spectator')
        self.assertEquals(updated_user['username'], 'global_spectator')
        self.assertEquals(updated_user['project_roles'], {})
        self.assertEquals(updated_user['global_role'], 'global_spectator')

        # Also a complete update with the PUT endpoint.
        response = api_client.get('/user_management/users/{0}/'
            .format(self.global_spectator.id))

        user_self = response.json()

        user_self['first_name'] = 'superglobal'
        user_self['last_name'] = 'superspectator'
        user_self['password'] = 'superpassword'

        response = api_client.put('/user_management/users/{0}/'
            .format(self.global_spectator.id),
            json.dumps(user_self),
            content_type='application/json')

        updated_user = response.json()

        self.assertEquals(response.status_code, status.HTTP_200_OK)
        self.assertEquals(updated_user['first_name'], 'superglobal')
        self.assertEquals(updated_user['last_name'], 'superspectator')
        self.assertEquals(updated_user['username'], 'global_spectator')
        self.assertEquals(updated_user['project_roles'], {})
        self.assertEquals(updated_user['global_role'], 'global_spectator')

    def test_update_of_nonexisting_user(self):
        api_client = Client()
        api_client.login(username=self.global_superuser.username,
            password=self.global_superuser.unhashed_password)

        # First verify that we get 404'd when using PATCH
        response = api_client.patch('/user_management/users/nn', json.dumps({
            'password': 'newpassword'
        }), content_type='application/json')

        self.assertEquals(response.status_code, status.HTTP_404_NOT_FOUND)

        # Also verify that we get a 404 when using put
        response = api_client.put('/user_management/users/daniel', json.dumps({
            'password': 'newpassword'
        }), content_type='application/json')

        self.assertEquals(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_user_update_other_without_permission(self):
        """
        Verify that an unauthenticated user is not allowed to update the
        credentials for a user, both through the patch and put methods.
        """
        new_user = User.objects.create_user('victim1',
            email='victim@kamaji.io')
        api_client = Client()
        url = '/user_management/users/{0}/'.format(self.global_superuser.id)

        update_payload = json.dumps({
            'username': 'not_a_victim',
            'password': 'password',
            'email': 'daniel@kamaji.io'
        })

        api_client.login(username=self.global_spectator.username,
            password=self.global_spectator.unhashed_password)

        response = api_client.patch(url, update_payload,
            content_type='application/json')

        self.assertEquals(response.status_code, status.HTTP_403_FORBIDDEN)

        response = api_client.post(url, update_payload,
            content_type='application/json')

        self.assertEquals(response.status_code, status.HTTP_403_FORBIDDEN)

        # Verify that no changes were made to the user
        updated_user = User.objects.get(id=new_user.id)

        self.assertEquals(updated_user.username, 'victim1')
        self.assertEquals(updated_user.email, 'victim@kamaji.io')

    def test_update_without_payload(self):
        """
        Verify that an attempted update with super user permissions without
        payload is disallowed.
        """
        api_client = Client()
        api_client.login(username=self.global_superuser.username,
            password=self.global_superuser.unhashed_password)

        response = api_client.put('/user_management/users/{0}/'.format(
            self.global_spectator.id), content_type='application/json')

        self.assertEquals(response.status_code, status.HTTP_400_BAD_REQUEST)

    # endregion

    # region user removal test cases
    def test_user_remove_without_permission(self):
        """
        Verify that removal of user is disallowed without proper permissions.
        """
        api_client = Client()
        api_client.login(username=self.global_spectator.username,
            password=self.global_spectator.unhashed_password)

        pre_user_count = len(User.objects.all())
        response = api_client.delete('/user_management/users/{0}/'
            .format(self.global_superuser.id))
        post_user_count = len(User.objects.all())

        self.assertEquals(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEquals(pre_user_count, post_user_count)

    def test_user_remove_self(self):
        """
        Verify that a user is never allowed to delete himself.
        """
        api_client = Client()
        api_client.login(username=self.global_superuser.username,
            password=self.global_superuser.unhashed_password)

        pre_user_count = len(User.objects.all())
        response = api_client.delete('/user_management/users/{0}/'
            .format(self.global_superuser.id))
        post_user_count = len(User.objects.all())

        self.assertEquals(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEquals(pre_user_count, post_user_count)

    def test_removal_of_missing_user(self):
        """
        Verify that an attempt to remove a missing user returns a 404.
        """
        api_client = Client()
        api_client.login(username=self.global_superuser.username,
            password=self.global_superuser)

        response = api_client.delete('/user_management/users/nouserhere')

        self.assertEquals(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_removal_without_id(self):
        """
        Verify that removal of a user without specifying the id generates an
        error.
        """
        api_client = Client()
        api_client.login(username=self.global_superuser.username,
            password=self.global_superuser.unhashed_password)

        allow_userlist_delete = Permission.create(
            name='allow_userlist_delete',
            views=[
                {
                    'view_name': 'UserList',
                    'delete': True
                }
            ]
        )

        self.administrator_role.permissions.add(allow_userlist_delete)

        pre_user_count = len(User.objects.all())
        response = api_client.delete('/user_management/users/')
        post_user_count = len(User.objects.all())

        self.assertEquals(response.status_code,
            status.HTTP_405_METHOD_NOT_ALLOWED)

        self.assertEquals(pre_user_count, post_user_count)

    def test_user_removal_without_login(self):
        """
        Verify that a unauthenticated user is disallowed to remove users.
        """
        api_client = Client()
        new_user = User.objects.create_user('victim')

        pre_user_count = len(User.objects.all())
        response = api_client.delete('/user_management/users/{0}/'
            .format(new_user.id))

        post_user_count = len(User.objects.all())

        self.assertEquals(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEquals(pre_user_count, post_user_count)

    # endregion
    # endregion

    def can_access_allowed_methods(self, user, view, handler,
            allowed_methods=(), project_id=None):
        for method in [x for x in self.all_methods
                       if x not in allowed_methods]:
            request = method('/Test/')
            request.user = user
            request.data = mock.MagicMock()
            request.data.project = project_id
            self.assertFalse(handler.has_permission(request, view))
        for method in allowed_methods:
            request = method('/Test/')
            request.user = user
            request.data = mock.MagicMock()
            request.data.project = project_id
            self.assertTrue(handler.has_permission(request, view))


class PermissionModelTest(TestCase):
    def setUp(self):
        self.permission = Permission.create(
            name='TestPermission',
            views=[
                {
                    'view_name': 'CreateView',
                    'create': True
                },
                {
                    'view_name': 'ReadView',
                    'read': True
                },
                {
                    'view_name': 'UpdateView',
                    'update': True
                },
                {
                    'view_name': 'DeleteView',
                    'delete': True
                }
            ]
        )

        self.all_methods = ['GET', 'POST', 'PUT', 'PATCH', 'DELETE',
                            'OPTIONS', 'HEAD']

    def test_allows_method(self):
        viewpermissions = self.permission.view_permissions
        self.allows(['POST'], viewpermissions.get(view_name='CreateView'))
        self.allows(['GET', 'OPTIONS', 'HEAD'],
            viewpermissions.get(view_name='ReadView'))
        self.allows(['PUT', 'PATCH'],
            viewpermissions.get(view_name='UpdateView'))
        self.allows(['DELETE'], viewpermissions.get(view_name='DeleteView'))

    def allows(self, methods, permission):
        for method in [x for x in self.all_methods if x not in methods]:
            self.assertFalse(permission.allows_method(method))
        for method in methods:
            self.assertTrue(permission.allows_method(method))


class UserTestCase(TestCase):
    def setUp(self):
        settings.CELERY_ALWAYS_EAGER = True
        settings.BROKER_BACKEND = 'memory'
        app.CELERY_ALWAYS_EAGER = True

        self.client = AuthenticatedJsonTestClient()

        self.sample = {
            "username": "kalle1",
            "first_name": "kalle",
            "last_name": "karlsson",
            "password": "qwe",
            "email": "kalle@karl.com"
        }

    def test_list_user(self):
        response, json_response = self.client.get('/user_management/users/')
        self.assertEqual(response.status_code, 200)

    def test_create_user_with_empty_ssh_key(self):
        response, json_response = self.client.post(
            '/user_management/users/',
            json.dumps(self.sample),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 201)

    def test_create_user_with_faulty_ssh_key(self):
        sample = self.sample.copy()
        sample['ssh_key'] = 'asdasd'
        response, json_response = self.client.post(
            '/user_management/users/',
            json.dumps(sample),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 400)


# Mock classes
class TestView1(APIView):
    pass


class TestView2(APIView):
    pass


class ViewPermissionConfigurationTestCase(TestCase):

    @classmethod
    def _get_kamaji_views(cls, urlpatterns):
        # Only check our own apps.
        apps = tuple(set(settings.INSTALLED_APPS) & set(os.listdir('.')))

        views = []
        for pattern in urlpatterns:
            if isinstance(pattern, RegexURLResolver):
                views.extend(cls._get_kamaji_views(pattern.url_patterns))
            elif isinstance(pattern, RegexURLPattern):
                module = pattern.callback.__module__
                # filter out all external views
                if module.split('.', 1)[0] in apps:
                    views.append(pattern.callback.view_class)

        return views

    @classmethod
    def _get_protected_kamaji_views(cls):
        root_urlconf = __import__(settings.ROOT_URLCONF)
        all_urlpatterns = root_urlconf.urls.urlpatterns

        views = cls._get_kamaji_views(all_urlpatterns)

        # Filter our all RedirectingViews as they should have
        # no permission_classes
        return filter(
            lambda view: not issubclass(view, RedirectView),
            views
        )

    @classmethod
    def setUpClass(cls):
        cls.views = cls._get_protected_kamaji_views()
        super(ViewPermissionConfigurationTestCase, cls).setUpClass()

    def test_all_views_has_permission_classes(self):
        for view in self.__class__.views:
            self.assertFalse(
                len(view.permission_classes) == 0,
                'View {0} has no permission classes.'.format(view.__name__)
            )

    def test_all_views_has_assigned_view_permissions(self):

        # Filter out all views with the AllowAny permission class.
        # As they don't have an attached ViewPermission
        views = filter(
            lambda view: AllowAny not in view.permission_classes,
            self.__class__.views
        )

        for view in views:
            self.assertTrue(
                ViewPermission.objects.filter(
                    view_name=view.__name__
                ).exists(),
                'View {0} has no ViewPermission '
                'assigned to it.'.format(view.__name__)
            )
