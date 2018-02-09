# -*- coding: utf-8 -*-
import json
import mock
import rados

from django.conf import settings
from django.core.management import call_command
from django.test import TestCase
from rest_framework import status

from api.celery import app
from fabric.models import (
    PhysicalNetwork, Node, Controller, SSHKey, Setting, CEPHCluster,
    CEPHClusterPool, Host, NTPSetting
)
from fabric.tasks import UpdateHardwareInventoryTask
from shared.exceptions import (
    ResourceInUseError, UnsupportedOperation, IllegalState
)
from shared.openstack2 import ConflictError
from shared.testclient import (
    AuthenticatedTestClient, AuthenticatedJsonTestClient
)
from fabric.models.models_nodes import HardwareInventory


class FabricLinksListTestCase(TestCase):
    links = {
        "computes_link": "http://testserver/fabric/computes/",
        "external_storage_root_link": "http://testserver/fabric/external_storage/",
        "controllers_link": "http://testserver/fabric/controllers/",
        "physical_networks_link": "http://testserver/fabric/physicalnetworks/",
        "nodes_link": "http://testserver/fabric/nodes/",
        "settings_link": "http://testserver/fabric/settings/",
        "zones_link": "http://testserver/fabric/zones/",
    }

    def setUp(self):
        self.client = AuthenticatedTestClient()

    def test_get_links_list(self):
        response = self.client.get('/fabric/')
        self.assertDictEqual(self.links, json.loads(response.content))


class UpdateHardwareInventoryTestCase(TestCase):
    """
    Test case for UpdateHardwareInventoryTask Celery task.
    """
    ansible_success = {
        'dark': {},
        'contacted': {
            '127.0.0.1': {
                'changed': False,
                'verbose_override': True,
                'ansible_facts': {
                    'ansible_hostname': 'kamaji',
                    'ansible_architecture': 'x86_64',
                },
                'invocation': {
                    'module_args': '',
                    'module_complex_args': {},
                    'module_name': 'setup',
                },
            }
        }
    }

    ansible_failed = {
        'contacted': {},
        'dark': {
            'hostname': {
                'failed': True,
                'msg': 'SSH Error: ssh: Could not resolve hostname '
                       'blabla.local: Name or service not known\nIt'
                       'is sometimes useful to re-run the command using'
                       '-vvvv, which prints SSH debug output to help '
                       'diagnose the issue.',
            },
        }
    }

    @mock.patch('fabric.models.models_nodes.UpdateHardwareInventoryTask')
    def populate(self, mock_hardware_inventory):
        with mock.patch('fabric.models.models_physicalnetworks.'
                        'ConfigureDHCPTask'):
            network = PhysicalNetwork.objects.create(
                name='local-127',
                subnet='127.0.0.0',
                prefix='24',
                gateway='127.0.0.1',
                range_start='127.0.0.10',
                range_end='127.0.0.40'
            )

        hardware_inventory = HardwareInventory.objects.create(inventory='{"cpu": 4}')
        Node.objects.create(
            node_type=Node.UNCONFIGURED,
            state="PENDING",
            ip_address='127.0.0.1',
            mac_address='23:a4:ff:ca:b2:d6',
            network=network,
            hardware_inventory=hardware_inventory
        )

    def setUp(self):
        """
        Setup environment and database for each test case.
        """
        settings.CELERY_ALWAYS_EAGER = True
        settings.BROKER_BACKEND = 'memory'
        app.CELERY_ALWAYS_EAGER = True

        self.task_queue_success_mock = mock.MagicMock()
        self.task_queue_success_mock.hostvars.__getitem__ = \
            lambda x, y: 'hostvars_mock'

        self.task_queue_fail_mock = mock.MagicMock()
        self.task_queue_fail_mock.hostvars.__getitem__ = \
            lambda x, y: 'hostvars_mock'
        self.task_queue_fail_mock._stats.dark = ['127.0.0.1']

        self.populate()

    @mock.patch('shared.ansible_tasks.TaskQueueManager')
    def test_update_node_data_on_success(self, manager_mock):
        """
        Simulate a successful Ansible job via Celery and assert
        the Celery task is successful.
        """
        manager_mock.return_value = self.task_queue_success_mock
        node = Node.objects.first()
        task = UpdateHardwareInventoryTask()
        result = task.delay(node)
        self.assertTrue(result.successful())
        self.assertFalse(result.failed())


class NodesTestCase(TestCase):
    sample_ansible_facts = '''{
        "ansible_memtotal_mb": "1024",
        "ansible_processor_count": "2",
        "ansible_devices": "{}"
    }'''

    def populate_ceph_cluster(self):
        CEPHCluster.objects.create(
            name='mock-ceph-cluster',
            cephx='True',
            uuid='af078d8f-4e99-4837-88bb-b1604c6563b6',
            fsid='c82a4f56-0082-4c55-b9fd-05b326eb5eda',
            mon_host='10.10.10.10',
            status=CEPHCluster.CONNECTION_CONNECTED,
            username='ceph-user',
            password='ceph-password'
        )

    @mock.patch('fabric.models.models_nodes.UpdateHardwareInventoryTask')
    def populate(self, mock_hardware_inventory):
        with mock.patch('fabric.models.models_physicalnetworks'
                        '.ConfigureDHCPTask'):
            self.sample_network = PhysicalNetwork.objects.create(
                name='local-192',
                subnet='192.168.0.0',
                prefix=24,
                gateway='192.168.0.1',
                range_start='192.168.0.10',
                range_end='192.168.0.50'
            )

        hardware_inventory = HardwareInventory.objects.create(inventory=self.sample_ansible_facts)
        self.node = Node.objects.create(
             ip_address='192.168.0.15',
             network=self.sample_network,
             node_type=Node.UNCONFIGURED,
             mac_address='aa:bb:cc:aa:bb:cc',
             hardware_inventory=hardware_inventory
        )

        self.populate_ceph_cluster()

    def setUp(self):
        settings.CELERY_ALWAYS_EAGER = True
        settings.BROKER_BACKEND = 'memory'
        app.CELERY_ALWAYS_EAGER = True
        self.populate()
        self.client = AuthenticatedTestClient()

    @classmethod
    @mock.patch('fabric.models.models_physicalnetworks.ConfigureDHCPTask')
    @mock.patch('fabric.models.models_settings.ConfigureNTPServersTask')
    def setUpTestData(cls, dhcp_mock, ntp_mock):
        call_command(
            'loadconfiguration',
            file='api/tests/test_configuration',
            testing=True
        )

    @mock.patch('fabric.tasks.UpdateHardwareInventoryTask.delay')
    def test_list_all_nodes(self, mock_hardware_inventory):
        mock_hardware_inventory.return_value = json.loads(
            self.sample_ansible_facts
        )
        response = self.client.get('/fabric/nodes/', follow=True)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.json()), 1)

    def test_list_all_unconfigured_nodes(self):
        response = self.client.get('/fabric/nodes/',
                                   {'node_type': 'unconfigured'},
                                   follow=True)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.json()), 1)

    @mock.patch('fabric.tasks.UpdateHardwareInventoryTask.delay')
    def test_create_new_node_with_correct_data(self, get_inventory_mock):
        response = self.client.post(
            '/fabric/nodes/',
            json.dumps({
                'ip_address': '192.168.0.12',
                'mac_address': '54:ee:75:6f:08:11',
                'prefix': '24'
            }), content_type='application/json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    @mock.patch('fabric.tasks.UpdateHardwareInventoryTask.delay')
    def test_create_new_node_without_active_ceph(self,
                                                 get_inventory_data_mock):
        get_inventory_data_mock.return_value \
            = self.sample_ansible_facts

        CEPHCluster.objects.all().delete()

        creation_response = self.client.post('/fabric/nodes/', json.dumps({
            'ip_address': '192.168.0.12',
            'mac_address': '54:ee:75:6f:08:11',
            'prefix': '24'
         }), content_type='application/json')

        created_node = creation_response.data

        created_node['node_type'] = 'compute'

        update_response = self.client.put(
            '/fabric/nodes/{0}/'.format(created_node['mac_address']),
            json.dumps(created_node),
            content_type='application/json'
        )

        self.assertEqual(update_response.status_code, 422)

        # Make sure that we restore the ceph cluster that we removed
        self.populate_ceph_cluster()

    def test_create_new_node_with_wrong_network(self):
        response = self.client.post('/fabric/nodes/',
                                    json.dumps({
                                        'ip_address': '192.168.2.12',
                                        'mac_address': '54:ee:75:6f:08:11',
                                        'prefix': '24'
                                    }), content_type='application/json')

        self.assertEqual(response.status_code,
                         status.HTTP_400_BAD_REQUEST)
        parsed_content = response.json()
        self.assertEqual(parsed_content, {
            "network": [
                "No configured network for ip_address \"192.168.2.12\""
            ]
        })

    def test_create_new_node_with_invalid_prefix(self):
        response = self.client.post('/fabric/nodes/',
                                    json.dumps({
                                        'ip_address': '192.168.2.12',
                                        'mac_address': '54:ee:75:6f:08:11',
                                        'prefix': '1337'
                                    }), content_type='application/json')

        self.assertEqual(response.status_code,
                         status.HTTP_400_BAD_REQUEST)

    @mock.patch('fabric.models.models_nodes.UpdateHardwareInventoryTask.delay')
    @mock.patch('fabric.tasks.AnsiblePlaybookTask.execute')
    def test_configure_node_with_correct_type(
            self,
            run_playbook_mock,
            mock_hardware_inventory):
        run_playbook_mock.returns = []

        response = self.client.put(
            '/fabric/nodes/{0}/'.format(self.node.mac_address),
            json.dumps({'node_type': 'compute'}),
            content_type='application/json')

        self.node.refresh_from_db()
        self.assertEquals(self.node.node_type, Node.COMPUTE)
        self.assertEquals(response.status_code, status.HTTP_200_OK)

    @mock.patch('shared.ansible_tasks._AnsibleTask.execute')
    def test_configure_node_with_incorrect_type(self, run_playbook_mock):
        run_playbook_mock.returns = []

        response = self.client.put('/fabric/nodes/{0}/'.format(
            self.node.mac_address),
            json.dumps({'node_type': 'batman'}),
            content_type='application/json')

        self.assertEquals(response.status_code, status.HTTP_400_BAD_REQUEST)

    @mock.patch('shared.ansible_tasks._AnsibleTask.execute')
    def test_configure_node_with_empty_data(self, run_playbook_mock):
        run_playbook_mock.returns = []

        response = self.client.put('/fabric/nodes/{0}/'.format(
            self.node.mac_address),
            json.dumps({}),
            content_type='application/json')

        self.assertEquals(response.status_code, status.HTTP_400_BAD_REQUEST)


class ControllerTestCase(TestCase):

    @mock.patch('fabric.models.models_nodes.UpdateHardwareInventoryTask')
    def populate(self, hardware_inventory_mock):
        self.controller1 = Controller.objects.create(
            name= 'controller-1',
            ip_address = '192.168.20.1'
        )

    def setUp(self):
        self.populate()
        self.client = AuthenticatedJsonTestClient()

    @mock.patch('fabric.models.models_nodes.UpdateHardwareInventoryTask')
    def test_add_controller(self, hardware_inventory_mock):
        controller_count_before = Controller.objects.count()
        response, json_data = self.client.post(
           '/fabric/controllers/',
           json.dumps({
               'name': 'controller-2',
               'ip_address': '192.168.20.2'
           }),
           content_type='application/json'
        )
        self.assertEqual(hardware_inventory_mock.return_value.delay.call_count, 1)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertGreater(Controller.objects.count(), controller_count_before)
        self.assertEqual(json_data['status'], 'ready_to_join_cluster')

    def test_add_duplicate_controller(self):
        controller_count_before = Controller.objects.count()
        response, _ = self.client.post(
            '/fabric/controllers/',
            json.dumps({
                'name': 'controller-1',
                'ip_address': '192.168.20.1'
            }),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(Controller.objects.count(), controller_count_before)

    @mock.patch('fabric.models.models_nodes.UpdateHardwareInventoryTask')
    def test_add_two_primary_controllers(self, hardware_inventory_mock):
        Controller.objects.all().delete()
        controller_count_before = Controller.objects.count()
        self.client.post(
            '/fabric/controllers/',
            json.dumps({
                'name': 'controller-1',
                'primary': True,
                'ip_address': '192.168.20.1'
            }),
            content_type='application/json'
        )
        response2, _ = self.client.post(
            '/fabric/controllers/',
            json.dumps({
                'name': 'controller-2',
                'primary': True,
                'ip_address': '192.168.20.2'
            }),
            content_type='application/json'
        )
        self.assertEqual(hardware_inventory_mock.return_value.delay.call_count, 1)
        self.assertEqual(response2.status_code, status.HTTP_400_BAD_REQUEST)

    @mock.patch('fabric.models.models_nodes.UpdateHardwareInventoryTask')
    def test_add_three_controllers(self, hardware_inventory_mock):
        controller_count_before = Controller.objects.count()
        self.client.post(
            '/fabric/controllers/',
            json.dumps({
                'name': 'controller-2',
                'primary': True,
                'ip_address': '192.168.20.2'
            }),
            content_type='application/json'
        )
        response2, _ = self.client.post(
            '/fabric/controllers/',
            json.dumps({
                'name': 'controller-3',
                'primary': False,
                'ip_address': '192.168.20.3'
            }),
            content_type='application/json'
        )
        self.assertEqual(hardware_inventory_mock.return_value.delay.call_count, 1)
        self.assertEqual(response2.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(Controller.objects.count(), controller_count_before + 1)

    @mock.patch('fabric.models.models_nodes.UpdateHardwareInventoryTask')
    def test_update_of_controller_details(self, hardware_inventory_mock):
        controller_count_before = Controller.objects.count()
        response, _ = self.client.put(
            '/fabric/controllers/1/',
            json.dumps({
                'name': 'controller-1',
                'primary': False,
                'ip_address': '192.168.20.1'
            }),
            content_type='application/json'
        )
        self.assertEqual(hardware_inventory_mock.return_value.delay.call_count, 1)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(Controller.objects.count(), controller_count_before)
        self.assertEqual(Controller.objects.get(id=1).name, 'controller-1')

    def test_delete_of_controller(self):
        controller_count_before = Controller.objects.count()
        self.assertIsInstance(Controller.objects.get(id=1), Controller)
        response = self.client.delete('/fabric/controllers/1/')
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertLess(Controller.objects.count(), controller_count_before)
        with self.assertRaises(Controller.DoesNotExist):
            Controller.objects.get(id=1)

    @mock.patch('fabric.models.models_nodes.UpdateHardwareInventoryTask')
    def test_get_active_controllers_when_theres_only_one(self, hardware_mock):
        Controller.objects.all().delete()
        c1 = Controller.objects.create(
            name='Primary',
            primary=True,
            ip_address='10.0.0.1',
            status=Controller.READY_TO_JOIN
        )
        active = Controller.active.all()
        self.assertListEqual(list(active), [c1])

    @mock.patch('fabric.models.models_nodes.UpdateHardwareInventoryTask')
    def test_get_active_controllers_secondary_not_clustered(self, hardware_mock):
        Controller.objects.all().delete()
        c1 = Controller.objects.create(
            name='Primary',
            primary=True,
            ip_address='10.0.0.1',
            status=Controller.READY_TO_JOIN
        )
        Controller.objects.create(
            name='Secondary',
            primary=False,
            ip_address='10.0.0.2',
            status=Controller.READY_TO_JOIN
        )
        active = Controller.active.all()
        self.assertListEqual(list(active), [c1])

    @mock.patch('fabric.models.models_nodes.UpdateHardwareInventoryTask')
    def test_get_active_controllers_all_clustered(self, hardware_mock):
        Controller.objects.all().delete()
        c1 = Controller.objects.create(
            name='Primary',
            primary=True,
            ip_address='10.0.0.1'
        )
        c2 = Controller.objects.create(
            name='Secondary',
            primary=False,
            ip_address='10.0.0.2'
        )
        c1.status = Controller.CLUSTERED
        c1.save()
        c2.status = Controller.CLUSTERED
        c2.save()
        active = Controller.active.all()
        self.assertListEqual(list(active), [c1, c2])

    @mock.patch('fabric.models.models_nodes.UpdateHardwareInventoryTask')
    def test_get_active_controller_addresses(self, hardware_mock):
        b1 = Host.objects.create(
            ip_address='127.0.0.1', type='boot', index=1
        )
        Host.objects.create(
            ip_address='127.0.0.2', type='boot', index=2
        )
        Host.objects.create(
            ip_address='127.0.0.3', type='osc', index=1
        )
        Host.objects.create(
            ip_address='127.0.0.4', type='osc', index=2
        )

        Controller.objects.all().delete()

        Controller.objects.create(
            name='Primary',
            primary=True,
            ip_address='10.0.0.1'
        )
        Controller.objects.create(
            name='Secondary',
            primary=False,
            ip_address='10.0.0.2'
        )

        hosts = Controller.active.get_addresses('boot')
        self.assertListEqual(list(hosts), [b1.ip_address])


class SettingsTestCase(TestCase):
    domain_expected_output = {'domain': 'test.org.'}
    resolver_expected_output = {'resolvers': ['192.168.0.6']}
    ntp_url_1 = '1.se.pool.ntp.org'
    ntp_url_2 = '2.se.pool.ntp.org'
    public_key = 'A super-duper public key'

    @mock.patch('fabric.models.models_settings.ConfigureNTPServersTask')
    def populate_all_settings(self, ntp_mock):
        Setting.objects.all().delete()
        Setting.objects.create(
            setting='ResolverSetting',
            value={'resolvers': ['192.168.0.1', '192.168.0.2']}
        )
        Setting.objects.create(
            setting='DomainSetting',
            value={'domain': 'test.org.'}
        )

        NTPSetting.objects.all().delete()
        NTPSetting.objects.create(address=SettingsTestCase.ntp_url_1)
        NTPSetting.objects.create(address=SettingsTestCase.ntp_url_2)

        SSHKey.objects.all().delete()
        SSHKey.objects.create(
            service=SSHKey.KAMAJI_SSH_KEY, key=self.public_key)

    def setUp(self):
        self.api_client = AuthenticatedJsonTestClient()
        self.populate_all_settings()

    @classmethod
    @mock.patch('fabric.models.models_physicalnetworks.ConfigureDHCPTask')
    @mock.patch('fabric.models.models_settings.ConfigureNTPServersTask')
    def setUpTestData(cls, dhcp_mock, ntp_mock):
        call_command(
            'loadconfiguration',
            file='api/tests/test_configuration',
            testing=True
        )

    def test_get_all_settings(self):
        # Can't get the extra args (follow=True) to work with the
        # AuthenticatedJsonTestClient so we use the simpler client here.
        response = AuthenticatedTestClient().get(
            '/fabric/settings', follow=True)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_get_single_setting_domain(self):
        response, json_content = \
            self.api_client.get('/fabric/settings/DomainSetting/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(json_content, self.domain_expected_output)

    def test_put_on_single_setting_domain(self):
        response, _ = self.api_client.put(
            '/fabric/settings/DomainSetting/',
            json.dumps({
                'domain': 'update.org'
            }),
            content_type='application/json'
        )
        self.assertEqual(response.status_code,
                         status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_patch_on_single_setting_domain(self):
        response, _ = self.api_client.patch(
            '/fabric/settings/DomainSetting/',
            json.dumps({'data': 'update.org', 'setting': 'DomainSetting'}),
            content_type='application/json'
        )
        self.assertEqual(response.status_code,
                         status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_put_update_resolvers_with_valid_data(self):
        response, json_content = self.api_client.put(
            '/fabric/settings/ResolverSetting/',
            json.dumps(
                {'resolvers': ['192.168.0.6']}
            ),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(json_content, self.resolver_expected_output)

    def test_put_update_resolvers_with_invalid_data(self):
        response, _ = self.api_client.put(
            '/fabric/settings/ResolverSetting/',
            json.dumps(
                {'resolvers': ['192.368.2.6']})
            ,
            content_type='application/json'
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_patch_update_resolvers_with_valid_data(self):
        response, json_content = self.api_client.patch(
            '/fabric/settings/ResolverSetting/',
            json.dumps(
                {'resolvers': ['192.168.0.6']}
            ),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(json_content, self.resolver_expected_output)

    def test_patch_update_resolvers_with_invalid_data(self):
        response, _ = self.api_client.patch(
            '/fabric/settings/ResolverSetting/',
            json.dumps(
                {'resolvers': ['192.368.2.6']}
            ),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_get_ntp(self):
        response, json_content = \
            self.api_client.get('/fabric/settings/NTPSetting/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ntp_urls = [server['address'] for server in json_content]
        self.assertTrue(self.ntp_url_1 in ntp_urls)
        self.assertTrue(self.ntp_url_2 in ntp_urls)

    @mock.patch('fabric.tasks.ConfigureNTPServersTask.__call__')
    def test_put_updates_status_to_active_on_success(self, call_mock):
        NTPSetting.objects.all().delete()
        response, json_response = self.api_client.post(
            '/fabric/settings/NTPSetting/',
            json.dumps({'address': self.ntp_url_1}),
            content_type='application/json'
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        response, json_response = self.api_client.post(
            '/fabric/settings/NTPSetting/',
            json.dumps({'address': self.ntp_url_2}),
            content_type='application/json'
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        ntp_server_1 = NTPSetting.objects.get(address=self.ntp_url_1)
        ntp_server_2 = NTPSetting.objects.get(address=self.ntp_url_2)

        self.assertEqual(ntp_server_1.status, NTPSetting.ACTIVE)
        self.assertEqual(ntp_server_2.status, NTPSetting.ACTIVE)

    @mock.patch('fabric.tasks.ConfigureNTPServersTask.execute')
    def test_put_updates_status_to_error_on_failure(self, execute_mock):
        execute_mock.side_effect = Exception('Internal Error')

        NTPSetting.objects.all().delete()
        response, json_response = self.api_client.post(
            '/fabric/settings/NTPSetting/',
            json.dumps({'address': self.ntp_url_1}),
            content_type='application/json'
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED
        )

        response, json_response = self.api_client.post(
            '/fabric/settings/NTPSetting/',
            json.dumps({'address': self.ntp_url_2}),
            content_type='application/json'
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED
        )

        ntp_server_1 = NTPSetting.objects.get(address=self.ntp_url_1)
        ntp_server_2 = NTPSetting.objects.get(address=self.ntp_url_2)

        self.assertEqual(ntp_server_1.status, NTPSetting.INTERNAL_ERROR)
        self.assertEqual(ntp_server_2.status, NTPSetting.INTERNAL_ERROR)

    def test_ntp_test_updates_connection_status_and_stratum(self):
        timestamp = 12312312.21323123
        responses = [
            SettingsTestCase.NTPResponse(2, timestamp),
            Exception('Connection Error'),
            Exception('Connection Error')
        ]

        with mock.patch(
                'fabric.models.models_settings.ntplib.NTPClient.request',
                new=self.__request_with_history(responses)
        ):
            response, json_response = self.api_client.post(
                '/fabric/settings/NTPSetting/action/',
                json.dumps({'action': 'test'}),
                content_type='application/json'
            )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(self.ntp_url_1 in json_response)
        self.assertTrue(self.ntp_url_2 in json_response)

        self.assertEqual(
            json_response[self.ntp_url_1]['connection_status'],
            NTPSetting.CONNECTION_UP)
        self.assertEqual(
            json_response[self.ntp_url_2]['connection_status'],
            NTPSetting.CONNECTION_ERROR)

        self.assertTrue('stratum' in json_response[self.ntp_url_1])

        ntp_server_1 = NTPSetting.objects.get(address=self.ntp_url_1)
        ntp_server_2 = NTPSetting.objects.get(address=self.ntp_url_2)

        self.assertEqual(ntp_server_1.connection_status, NTPSetting.CONNECTION_UP)
        self.assertEqual(
            ntp_server_2.connection_status,
            NTPSetting.CONNECTION_ERROR
        )

        self.assertEqual(2, ntp_server_1.last_test_stratum)
        self.assertTrue(hasattr(ntp_server_2, 'last_test_stratum'))

    def test_verify_ntp_object_without_address_fails(self):
        response, _ = self.api_client.post(
            '/fabric/settings/NTPSetting/',
            json.dumps({"no-address-here": "ntp.server.tld"}),
            content_type='application/json'
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_ntp_verify_url_not_hostname_fails(self):
        response, _ = self.api_client.post(
            '/fabric/settings/NTPSetting/',
            json.dumps({'address': "!!!???"}),
            content_type='application/json'
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_publickey_returns_key(self):
        response, json_content = self.api_client.get(
            '/fabric/settings/PublicKey/'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(json_content['key'], self.public_key)

    def __request_with_history(self, history):
        @staticmethod
        def request(url):
            response = history.pop(0)
            if isinstance(response, Exception):
                raise response
            return response

        return request

    class NTPResponse(object):
        def __init__(self, stratum, tx_time):
            self.stratum = stratum
            self.tx_time = tx_time


class CEPHClusterTestCase(TestCase):
    ansible_success = {
        'dark': {},
        'contacted': {
            '127.0.0.1': {
                'changed': False,
                'verbose_override': True,
                'ansible_facts': {
                    'ansible_hostname': 'kamaji',
                    'ansible_architecture': 'x86_64',
                },
                'invocation': {
                    'module_args': '',
                    'module_complex_args': {},
                    'module_name': 'setup',
                },
            }
        }
    }

    def setUp(self):
        settings.CELERY_ALWAYS_EAGER = True
        settings.BROKER_BACKEND = 'memory'
        app.CELERY_ALWAYS_EAGER = True

        self.api_client = AuthenticatedJsonTestClient()

        self.sample_cluster = CEPHCluster.objects.create(
            name='test-cluster-01',
            cephx=False,
            fsid='5acff144-de18-4a0e-8fd5-1d8dfc50ceb7',
            mon_host='10.10.10.10',
            username='test-user',
            password='password'
        )

        self.sample_pool = CEPHClusterPool.objects.create(
            pool='pool_name',
            type='volume',
            cluster=self.sample_cluster
        )

    @classmethod
    @mock.patch('fabric.models.models_physicalnetworks.ConfigureDHCPTask')
    @mock.patch('fabric.models.models_settings.ConfigureNTPServersTask')
    def setUpTestData(cls, dhcp_mock, ntp_mock):
        call_command(
            'loadconfiguration',
            file='api/tests/test_configuration',
            testing=True
        )

    def test_get_ceph_cluster(self):
        response, response_content = self.api_client.get(
            '/fabric/external_storage/ceph/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsInstance(response_content, list)
        self.assertEqual(len(response_content), 1)

    def test_create_new_ceph_cluster(self):
        CEPHCluster.objects.all().delete()

        response, response_content = self.api_client.post(
            '/fabric/external_storage/ceph/',
            {
                'name': 'test-cluster-01',
                'cephx': True,
                'fsid': '260ac3e6-68a5-4d0b-b4c7-eab2eba711ea',
                'mon_host': '10.20.30.40',
                'username': 'a-kamaji-user',
                'password': 'password'
            }
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_create_additional_ceph_cluster_is_denied(self):
        response, response_content = self.api_client.post(
            '/fabric/external_storage/ceph/',
            json.dumps({
                'name': 'test-cluster-01',
                'cephx': True,
                'fsid': '260ac3e6-68a5-4d0b-b4c7-eab2eba711ea',
                'mon_host': '10.20.30.40',
                'username': 'a-kamaji-user',
                'password': 'password'
            }),
            content_type='application/json'
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    @mock.patch('shared.ansible_tasks.PlaybookExecutor')
    def test_connect_cluster(self, playbook_mock):
        executor = mock.MagicMock()
        executor.run = mock.MagicMock(return_value=3)
        playbook_mock.return_value = executor

        response, response_content = self.api_client.post(
            '/fabric/external_storage/ceph/test-cluster-01/action/',
            json.dumps({'action': 'connect'}),
            content_type='application/json'
        )

        cluster = CEPHCluster.objects.get(name='test-cluster-01')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(cluster.status, CEPHCluster.CONNECTION_CONNECTED)

    def test_delete_cluster(self):
        pre_cluster_count = CEPHCluster.objects.count()

        response = self.api_client.delete(
            '/fabric/external_storage/ceph/test-cluster-01/')

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

        post_cluster_count = CEPHCluster.objects.count()

        self.assertEqual(pre_cluster_count, post_cluster_count + 1)

    def test_update_cluster(self):
        response, response_content = self.api_client.put(
            '/fabric/external_storage/ceph/test-cluster-01/',
            json.dumps({
                'name': 'new-test-cluster',
                'cephx': False,
                'fsid': 'e7b72070-62b2-4270-b818-0a675f2405ba',
                'username': 'another-kamaji-user',
                'password': 'new-password',
                'mon_host': '11.12.13.14'
            }),
            content_type='application/json'
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_get_cluster_pools(self):
        _, cluster = self.api_client.get(
            '/fabric/external_storage/ceph/test-cluster-01/'
        )

        response, pools = self.api_client.get(cluster['shares_link'])

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsInstance(pools, list)
        self.assertEqual(len(pools), CEPHCluster.objects.first().pools.count())

    def test_add_pool(self):
        pre_pool_count = CEPHClusterPool.objects.count()

        _, cluster = self.api_client.get(
            '/fabric/external_storage/ceph/test-cluster-01/'
        )

        response, pools = self.api_client.post(cluster['shares_link'], {
            'pool': 'new-pool',
            'type': 'image'
        })

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIsInstance(pools, dict)

        post_pool_count = CEPHClusterPool.objects.count()

        self.assertEqual(pre_pool_count + 1, post_pool_count)

    def test_get_single_pool(self):
        response, response_content = self.api_client.get(
            '/fabric/external_storage/shares/pool_name/'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_get_single_non_existing_pool(self):
        response, response_content = self.api_client.get(
            '/fabric/external_storage/shares/nonexisting/'
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_connection_on_non_existing_cluster(self):
        response, _ = self.api_client.get(
            '/fabric/external_storage/ceph/nonexistingcluster/test/')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    @mock.patch('fabric.models.models_storage.rados.Rados')
    def test_connection_test_succeeds(self, rados_mock):
        instance = rados_mock.return_value
        instance.state = 'connected'
        instance.connect.return_value = None
        response, response_content = self.api_client.post(
            '/fabric/external_storage/ceph/{0}/action/'
            .format(self.sample_cluster.name),
            json.dumps({'action': 'test'}),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response_content['status'], 'connected')

    @mock.patch('fabric.models.models_storage.rados.Rados')
    def test_connection_test_general_error_returns_error(self, rados_mock):
        instance = rados_mock.return_value
        instance.connect.side_effect = rados.Error('Rados Error')

        response, response_content = self.api_client.post(
            '/fabric/external_storage/ceph/{0}/action/'
                .format(self.sample_cluster.name),
            json.dumps({'action': 'test'}),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response_content['status'], 'error')

    @mock.patch('fabric.models.models_storage.rados.Rados')
    def test_connection_test_interrupted_error_returns_error(self, rados_mock):
        instance = rados_mock.return_value
        instance.connect.side_effect = \
            rados.InterruptedOrTimeoutError('Interrupted')

        response, response_content = self.api_client.post(
            '/fabric/external_storage/ceph/{0}/action/'
                .format(self.sample_cluster.name),
            json.dumps({'action': 'test'}),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response_content['status'], 'error')


class PhysicalNetworkTestCase(TestCase):
    def setUp(self):
        self.api_client = AuthenticatedJsonTestClient()
        self.api_endpoint = '/fabric/physicalnetworks/'

        self.sample_network = {
            'name': 'local-10',
            'subnet': '10.10.0.0',
            'prefix': 24,
            'gateway': '10.10.0.1',
            'range_start': '10.10.0.10',
            'range_end': '10.10.0.50',
            'type': 'compute_network'
        }

        with mock.patch('fabric.models.models_physicalnetworks.'
                        'ConfigureDHCPTask'):
            PhysicalNetwork.objects.create(**self.sample_network)

        self.valid_network = {
            'name': 'local-192',
            'subnet': '192.168.0.0',
            'prefix': 24,
            'gateway': '192.168.0.1',
            'range_start': '192.168.0.100',
            'range_end': '192.168.0.200',
            'type': 'compute_network'
        }

        self.controller_network = {
            'name': 'controller_network',
            'subnet': '10.20.30.0',
            'prefix': 24,
            'gateway': '10.20.30.1',
            'range_start': '10.20.30.10',
            'range_end': '10.20.30.50',
            'type': 'controller_network'
        }

    def test_get_compute_networks(self):
        response, response_content = self.api_client.get(self.api_endpoint)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsInstance(response_content, list)
        self.assertEqual(len(response_content), 1)

    def test_get_compute_network_single(self):
        response, response_content = self.api_client.get(
            '{0}1/'.format(self.api_endpoint)
        )

        expected_result = self.sample_network.copy()
        expected_result['id'] = 1

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response_content, expected_result)

    @mock.patch('fabric.models.models_physicalnetworks.ConfigureDHCPTask')
    def test_put_compute_network(self, configure_dhcp_mock):
        expected_result = self.sample_network.copy()
        expected_result['id'] = 1
        expected_result['range_start'] = '10.10.0.20'

        get_response, get_response_content = self.api_client.get(
            '{0}1/'.format(self.api_endpoint)
        )

        get_response_content['range_start'] = '10.10.0.20'

        response, response_content = self.api_client.put(
            '{0}1/'.format(self.api_endpoint),
            json.dumps(get_response_content),
            content_type='application/json'
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response_content, expected_result)

    @mock.patch('fabric.models.models_physicalnetworks.ConfigureDHCPTask')
    def test_add_compute_network(self, configure_dhcp_mock):
        response, response_content = self.api_client.post(
            self.api_endpoint, self.valid_network
        )

        expected_result = self.valid_network.copy()
        expected_result['id'] = 2

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response_content, expected_result)

    @mock.patch('fabric.models.models_physicalnetworks.ConfigureDHCPTask')
    def test_add_compute_network_without_range(self, configure_dhcp_mock):
        network = self.valid_network.copy()
        network.pop("range_start", None)
        network.pop("range_end", None)

        response, response_content = self.api_client.post(
            self.api_endpoint, network
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    @mock.patch('fabric.models.models_physicalnetworks.ConfigureDHCPTask')
    def test_add_compute_network_without_range_and_gateway_outside_network(self, configure_dhcp_mock):
        network = self.valid_network.copy()
        network.pop("range_start", None)
        network.pop("range_end", None)
        network['gateway'] = '192.168.0.0'

        response, response_content = self.api_client.post(
            self.api_endpoint, network
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_add_compute_network_invalid_prefix(self):
        network = self.valid_network.copy()
        network['prefix'] = 37
        expected_error = {"prefix": ["'37' is not a valid network prefix."]}

        response, response_content = self.api_client.post(
            self.api_endpoint, network
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response_content, expected_error)

    def test_add_compute_network_invalid_subnet(self):
        network = self.valid_network.copy()
        network['subnet'] = '12x.242.x2x'
        expected_error = {"subnet": ["Enter a valid IPv4 address."]}

        response, response_content = self.api_client.post(
            self.api_endpoint, network
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response_content, expected_error)

    def test_add_compute_network_gateway_not_in_range(self):
        network = self.valid_network.copy()
        network['gateway'] = '192.168.0.0'
        expected_error = {
            "subnet": [
                "'192.168.0.0' is not within the "
                "'192.168.0.0/24' network range"
            ],
            "prefix": [
                "'192.168.0.0' is not within the "
                "'192.168.0.0/24' network range"
            ]
        }

        response, response_content = self.api_client.post(
            self.api_endpoint, network
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response_content, expected_error)

    def test_add_compute_network_range_start_not_in_range(self):
        network = self.valid_network.copy()
        network['range_start'] = '192.168.2.100'
        expected_error = {
            u"subnet": [
                u"'192.168.2.100' is not within the "
                u"'192.168.0.0/24' network range"
            ],
            u"prefix": [
                u"'192.168.2.100' is not within the "
                u"'192.168.0.0/24' network range"
            ]
        }

        response, response_content = self.api_client.post(
            self.api_endpoint, network
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response_content, expected_error)

    def test_add_compute_network_range_start_lower_than_range_end(self):
        network = self.valid_network.copy()
        network['range_start'] = '192.168.0.150'
        network['range_end'] = '192.168.0.100'
        expected_error = {
            "range_start": [
                "Range start has to be a lower address than range end."
            ],
            "range_end": [
                "Range start has to be a lower address than range end."
            ]
        }

        response, response_content = self.api_client.post(
            self.api_endpoint, network
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response_content, expected_error)

    def test_add_network_gateway_inside_range(self):
        network = self.valid_network.copy()
        network['gateway'] = '192.168.0.151'
        network['range_start'] = '192.168.0.150'
        network['range_end'] = '192.168.0.156'
        expected_errors = ["gateway"]

        response, response_content = self.api_client.post(
            self.api_endpoint, network
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response_content.keys(), expected_errors)

    def test_add_network_only_range_end_specified(self):
        network = self.valid_network.copy()
        network.pop('range_start')
        expected_errors = ["range_start"]

        response, response_content = self.api_client.post(
            self.api_endpoint, network
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response_content.keys(), expected_errors)

    def test_add_network_only_range_start_specified(self):
        network = self.valid_network.copy()
        network.pop('range_end')
        expected_errors = ["range_end"]

        response, response_content = self.api_client.post(
            self.api_endpoint, network
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response_content.keys(), expected_errors)

    @mock.patch('fabric.models.models_physicalnetworks.ConfigureDHCPTask')
    def test_unique_model_fields(self, configure_dhcp_mock):
        self.api_client.post(self.api_endpoint, self.valid_network)
        response, response_content = self.api_client.post(
            self.api_endpoint, self.valid_network
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertListEqual(
            response_content.keys(),
            ['subnet', 'name', 'gateway']
        )

    @mock.patch('fabric.models.models_physicalnetworks.ConfigureDHCPTask')
    @mock.patch('fabric.models.models_physicalnetworks.fabric.models.'
                'Node.objects.all')
    def test_remove_networks_with_added_computes(self,
                                                 node_all_mock,
                                                 configure_dhcp_mock):
        node_all_mock.return_value = [
            Node(ip_address='10.10.10.10'),
            Node(ip_address='10.10.20.10'),
            Node(ip_address='192.168.100.100'),
            Node(ip_address='10.10.10.1')
        ]

        network = PhysicalNetwork.objects.create(
            name='test-network',
            subnet='10.10.10.0',
            prefix=24,
            gateway='10.10.10.1',
            range_start='10.10.10.10',
            range_end='10.10.10.20'
        )

        with self.assertRaises(ResourceInUseError):
            network.delete()

    @mock.patch('fabric.models.models_physicalnetworks.ConfigureDHCPTask')
    @mock.patch('fabric.models.models_physicalnetworks.fabric.models.'
                'Node.objects.all')
    def test_remove_network_with_compute_through_view(self,
                                                      node_all_mock,
                                                      configure_dhcp_mock):

        node_all_mock.return_value = [
            Node(ip_address='10.10.10.10'),
            Node(ip_address='10.10.20.10'),
            Node(ip_address='192.168.100.100'),
            Node(ip_address='10.10.10.1')
        ]

        network = PhysicalNetwork.objects.create(
            name='test-network',
            subnet='10.10.10.0',
            prefix=24,
            gateway='10.10.10.1',
            range_start='10.10.10.10',
            range_end='10.10.10.20'
        )

        client = AuthenticatedJsonTestClient()
        result = client.delete('/fabric/physicalnetworks/{0}/'.format(
            network.id))

        self.assertEqual(result.status_code, 400)

    @mock.patch('fabric.models.models_physicalnetworks.ConfigureDHCPTask')
    @mock.patch('fabric.models.models_physicalnetworks.fabric.models.'
                'Node.objects.all')
    def test_remove_networks_without_added_computes(self,
                                                    node_all_mock,
                                                    configure_dhcp_mock):
        node_all_mock.return_value = [
            Node(ip_address='10.10.10.10'),
            Node(ip_address='10.10.20.10'),
            Node(ip_address='192.168.100.100'),
            Node(ip_address='10.10.10.1')
        ]

        # This network shouldn't match any of the nodes above.
        network = PhysicalNetwork.objects.create(
            name='test-network',
            subnet='10.10.30.0',
            prefix=24,
            gateway='10.10.30.1',
            range_start='10.10.30.10',
            range_end='10.10.30.20'
        )

        network_pre_count = PhysicalNetwork.objects.count()
        network.delete()
        network_post_count = PhysicalNetwork.objects.count()

        self.assertEqual(network_pre_count, network_post_count + 1)

    @mock.patch('fabric.models.models_physicalnetworks.ConfigureDHCPTask')
    def test_remove_controller_networks(self, dhcp_mock):
        self.api_client.post(self.api_endpoint, self.valid_network)

        response, response_content = self.api_client.post(
            self.api_endpoint, self.controller_network
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        # Remove via endpoint
        del_response = self.api_client.delete(
                    '{0}{1}/'.format(
                        self.api_endpoint,
                        response_content['id']
                    )
                )

        self.assertEqual(del_response.status_code, status.HTTP_400_BAD_REQUEST)

        # Remove via model
        with self.assertRaises(UnsupportedOperation):
            PhysicalNetwork.controller_networks.first().delete()


class HostTestCase(TestCase):
    @mock.patch('fabric.models.models_nodes.UpdateHardwareInventoryTask')
    def setUp(self, update_hardware_mock):
        Controller.objects.create(
            name='controller01',
            primary=True,
            ip_address='10.10.10.10',
        )

        Controller.objects.create(
            name='controller02',
            primary=False,
            ip_address='20.20.20.20'
        )

    def test_populate_primary_controller_mapping(self):
        controller01 = Controller.objects.get(name='controller01')
        controller02 = Controller.objects.get(name='controller02')

        self.assertEqual(controller01.host_map.count(), 0)
        self.assertEqual(controller02.host_map.count(), 0)

        Host.objects.create(
            ip_address='10.10.10.11',
            type='bitcoin',
            index=1
        )

        self.assertEqual(controller01.host_map.count(), 1)
        self.assertEqual(controller02.host_map.count(), 0)

    def test_populate_secondary_controller_mapping(self):
        controller01 = Controller.objects.get(name='controller01')
        controller02 = Controller.objects.get(name='controller02')

        self.assertEqual(controller01.host_map.count(), 0)
        self.assertEqual(controller02.host_map.count(), 0)

        Host.objects.create(
            ip_address='10.10.10.11',
            type='bitcoin',
            index=2
        )

        self.assertEqual(controller01.host_map.count(), 0)
        self.assertEqual(controller02.host_map.count(), 1)


class InstanceActionTestCase(TestCase):
    @mock.patch('shared.openstack2.models.OSModel._session')
    def test_stop_instance(self, post_mock):
        instance = Instance(
            id=1,
            name='instance01',
            status='ACTIVE'
        )

        instance.shut_down()

        post_mock.post.assert_called_once_with(
            json={'os-stop': {}},
            path=('', 'action')
        )

    @mock.patch('shared.openstack2.models.OSModel._session')
    def test_start_instance(self, post_mock):
        instance = Instance(
            id=1,
            name='instance02',
            status='SHUTOFF'
        )

        instance.start()

        post_mock.post.assert_called_once_with(
            json={'os-start': {}},
            path=('', 'action')
        )

    def test_restart_instance(self):
        instance = Instance(
            id=1,
            name='instance02',
            status='ACTIVE'
        )

        # Test reboot without specified type
        with mock.patch('shared.openstack2.models.OSModel._session') \
                as post_mock:
            instance.reboot()

            post_mock.post.assert_called_once_with(
                json={'reboot': {
                    'type': 'soft'
                }},
                path=('', 'action')
            )

        # Test reboot with specified soft reboot
        with mock.patch('shared.openstack2.models.OSModel._session') \
                as post_mock:
            instance.reboot(type=Instance.RebootType.SOFT)

            post_mock.post.assert_called_once_with(
                json={'reboot': {
                    'type': 'soft'
                }},
                path=('', 'action')
            )

        # Test reboot with specified hard reboot
        with mock.patch('shared.openstack2.models.OSModel._session') \
                as post_mock:
            instance.reboot(type=Instance.RebootType.HARD)

            post_mock.post.assert_called_once_with(
                json={'reboot': {
                    'type': 'hard'
                }},
                path=('', 'action')
            )

    @mock.patch('shared.openstack2.models.OSModel._session')
    def test_unable_to_stop_shutoff_instance(self, post_mock):
        instance = Instance(
            id=1,
            name='instance02',
            status='SHUTOFF'
        )

        with self.assertRaises(IllegalState):
            instance.shut_down()

    @mock.patch('shared.openstack2.models.OSModel._session')
    def test_unable_to_reboot_shutoff_instance(self, post_mock):
        instance = Instance(
            id=1,
            name='instance02',
            status='SHUTOFF'
        )

        with self.assertRaises(IllegalState):
            instance.reboot()

        with self.assertRaises(IllegalState):
            instance.reboot(type=Instance.RebootType.SOFT)

        with self.assertRaises(IllegalState):
            instance.reboot(type=Instance.RebootType.HARD)

    @mock.patch('shared.openstack2.models.OSModel._session')
    def test_unable_to_start_active_instance(self, post_mock):
        instance = Instance(
            id=1,
            name='instance02',
            status='ACTIVE'
        )

        with self.assertRaises(IllegalState):
            instance.start()

    @mock.patch('shared.openstack2.models.OSModel._session')
    def test_handling_openstack_error(self, post_mock):
        post_mock.post.side_effect = ConflictError

        instance = Instance(
            id=1,
            name='instance02',
            status='ACTIVE'
        )

        with self.assertRaises(IllegalState):
            instance.shut_down()
