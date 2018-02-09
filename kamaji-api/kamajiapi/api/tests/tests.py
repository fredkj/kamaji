# -*- coding: utf-8 -*-
import ast
import os

from django.db import DatabaseError
from django.core.management import call_command
from django.test import Client, TestCase
from django.forms.models import model_to_dict
from django.conf import settings
from rest_framework import status
from rest_framework_jwt import utils
from django.contrib.auth.models import User

from fabric.models import Credential, SSHKey, Host, Setting, PhysicalNetwork
from shared.exceptions import KamajiOpenStackError

import api
import mock


class JSONWebTokenTestCase(TestCase):
    """
    Test case test implementation of JSON Web Token.
    """

    def setUp(self):
        self.user = User.objects.create_user(
            username='test_user',
            email='morgan@pwny.se',
            password='qwe123'
        )
        self.http_client = Client()

    def test_post_to_acquire_token_from_token_endpoint(self):
        """
        Authenticate against JWT token endpoint and acquire a token.
        """
        response = self.http_client.post('/auth/token/',
                                         data={'username': 'test_user',
                                               'password': 'qwe123'},
                                         follow=True)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_get_on_endpoint_without_login_token(self):
        """
        Test to GET on endpoint without a JWT token.
        """
        response = self.http_client.get('/fabric/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_get_on_endpoint_with_login_token(self):
        """
        Test GET on endpoint with a valid JWT hence failing permissions.
        """
        # Create token manually
        payload = utils.jwt_payload_handler(self.user)
        token = utils.jwt_encode_handler(payload)

        auth = 'JWT {0}'.format(token)
        response = self.http_client.get(
            '/fabric/settings/', HTTP_AUTHORIZATION=auth, format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_get_on_endpoint_with_expired_token(self):
        """
        Test GET on endpoint with an expired token.
        """
        # Create token manually with expiration time of 1 second.
        payload = utils.jwt_payload_handler(self.user)
        payload['exp'] = 1
        token = utils.jwt_encode_handler(payload)

        auth = 'JWT {0}'.format(token)
        response = self.http_client.get(
            '/fabric/', HTTP_AUTHORIZATION=auth, format='json'
        )
        self.assertEqual(response.data['detail'], 'Signature has expired.')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class LoadConfigurationTest(TestCase):
    expected_password = 'ponies_password'
    expected_ssh = 'ponies_ssh'
    expected_ip = 'ponies_ip'

    expected_hosts = {
        'boot1': '192.168.50.57',
        'boot2': '192.168.50.67',
        'db1': '192.168.50.52',
        'db2':	'192.168.50.62',
        'lb1':	'192.168.50.50',
        'lb2':	'192.168.50.60',
        'mq1':	'192.168.50.51',
        'mq2':	'192.168.50.61',
        'ns1':	'192.168.50.53',
        'ns2':	'192.168.50.63',
        'osc1': '192.168.50.55',
        'osc2': '192.168.50.65',
        'osn1': '192.168.50.56',
        'osn2': '192.168.50.66',
        'controller1': '192.168.50.10',
        'controller2': '192.168.50.11',
        'web1': '192.168.50.54',
        'web2': '192.168.50.64',
        'vip': '192.168.50.15'
    }

    expected_ntp = [{'url': '0.se.pool.ntp.org'},
                    {'url': '1.se.pool.ntp.org'},
                    {'url': '2.se.pool.ntp.org'}]
    expected_domain = 'kamaji.company.com'
    expected_resolvers = ['8.8.8.8', '8.8.4.4']

    expected_controller_network = {
        'name': 'controller_network',
        'subnet': '192.168.50.0',
        'prefix': 24,
        'gateway': '192.168.50.1',
        'range_start': '192.168.50.2',
        'range_end': '192.168.50.254',
        'type': 'controller_network'
    }

    @mock.patch('fabric.models.models_physicalnetworks.ConfigureDHCPTask')
    def test_models_are_updated_with_correct_data(self, configure_dhcp_mock):
        test_file = os.getcwd() + '/api/tests/test_configuration'
        try:
            call_command('loadconfiguration', file=test_file, testing=True)
        except KamajiOpenStackError:
            # TODO: Mock the openstack integration so we don't have to
            # catch here.
            pass

        for credential in Credential.objects.all():
            self.assertEqual(credential.password, self.expected_password)
        self.assertEqual(Credential.objects.count(), 18)

        for key in SSHKey.objects.all():
            self.assertEqual(key.key, self.expected_ssh)
        self.assertEqual(SSHKey.objects.count(), 1)

        for host in Host.objects.all():
            self.assertEqual(host.ip_address,
                             self.expected_hosts[host.hostname])
        self.assertEqual(Host.objects.count(), len(self.expected_hosts))

        for obj in Setting.objects.all():
            if obj.setting == 'DomainSetting':
                self.assertEqual(obj.domain, self.expected_domain)
            elif obj.setting == 'ResolverSetting':
                self.assertListEqual(obj.resolvers, self.expected_resolvers)

        controller_network_dict = model_to_dict(
            PhysicalNetwork.controller_networks.first(),
            exclude=['id']
        )

        self.assertDictEqual(
            self.expected_controller_network,
            controller_network_dict
        )


class StatusViewTest(TestCase):
    def setUp(self):
        self.domain_setting = Setting.objects.create(
            setting='DomainSetting',
            data='test.i.kamaji.io'
        )

        self.http_client = Client()
        self.api = api
        self.commit = self.api.__commit__

    def tearDown(self):
        if not hasattr(self.api, '__commit__'):
            self.api.__commit__ = self.commit

    def test_get_on_endpoint_with_success(self):
        response = self.http_client.get('/status/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_get_on_endpoint_with_object_not_found(self):
        self.domain_setting.delete()
        response = self.http_client.get('/status/')

        self.assertEqual(
            response.status_code,
            status.HTTP_500_INTERNAL_SERVER_ERROR
        )

    @mock.patch("fabric.views.Setting.objects.get")
    def test_get_on_endpoint_with_database_error(self, cursor_wrapper):
        cursor_wrapper.side_effect = DatabaseError
        response = self.http_client.get('/status/')

        self.assertEqual(
            response.status_code,
            status.HTTP_500_INTERNAL_SERVER_ERROR
        )

    def test_get_api_version_without_commit(self):
        delattr(self.api, '__commit__')
        response = self.http_client.get('/status/')

        self.assertEqual(
            response.data['api-version'],
            self.api.__version__
        )

    def test_get_api_version_with_commit(self):
        response = self.http_client.get('/status/')
        expected_version = '{0} ({1})'.format(
            self.api.__version__,
            self.api.__commit__
        )

        self.assertEqual(
            response.data['api-version'],
            expected_version
        )
