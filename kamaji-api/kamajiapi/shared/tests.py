# -*- coding: utf-8 -*-
from datetime import datetime

import mock
from django.core.validators import validate_ipv4_address
from django.core.management import call_command
from django.test import TestCase
from rest_framework import serializers
from unittest import TestCase as UnitTestCase

from fabric.models import Node, PhysicalNetwork, Setting, CEPHCluster
from fabric.tasks import (
    ConfigureComputeTask, ConfigureDHCPTask, UpdateHardwareInventoryTask
)
from shared.ansible_tasks import (
    _AnsibleTask, AnsibleRunnerTask, AnsiblePlaybookTask
)
from shared.exceptions import (
    AnsibleHostsUnavailableError, AnsiblePlaybookError,
    InvalidSSHKeyError)
from shared.rest_validators import (
    validate_mac_address, ValidationAggregator, IsNodeType, Not,
    validate_ipv4_network, ContainedIn, validate_ssh_key, IsSSHKey)
from shared.rollbacks import Rollbacks
from fabric.models.models_nodes import HardwareInventory


class AnsibleRunnerValidationTestCase(TestCase):
    """
    Test cases for Ansible Runner validation
    """
    def test_raises_exception_when_connection_fails(self):
        """
        Test to raise an exception if Ansible cannot reach
        the specified host
        """
        response = mock.MagicMock()
        response.dark = {
            '127.0.0.1': 1
        }

        self.assertRaises(
            AnsibleHostsUnavailableError,
            AnsibleRunnerTask.validate,
            response
        )

    def test_raises_exception_when_invalid_module(self):
        """
        Test to raise an exception if the Ansible module does not
        exists
        """
        response = mock.MagicMock()
        response.failures = {
            '127.0.0.1': 1
        }

        self.assertRaises(
            AnsiblePlaybookError,
            AnsibleRunnerTask.validate,
            response
        )


class AnsibleRunnerTestCase(TestCase):
    """
    Test cases to test Ansible runners.
    """
    def setUp(self):
        """
        A setup sequence that is built for every test case.
        """
        self.ip_address = '1.2.3.4'

        self.task_queue_success_mock = mock.MagicMock()
        self.task_queue_success_mock.hostvars.__getitem__ = \
            lambda x, y: {'ansible_architecture': 'x86_64'}

        self.task_queue_fail_mock = mock.MagicMock()
        self.task_queue_fail_mock.hostvars.__getitem__ = \
            lambda x, y: 'hostvars_mock'
        self.task_queue_fail_mock._stats.dark = ['127.0.0.1']

    @mock.patch('shared.ansible_tasks.TaskQueueManager')
    def test_get_inventory_data_raises_exception_no_host(self, manager_mock):
        """
        Test to raise an exception if a Ansible job fails when no hosts are
        available
        """
        manager_mock.return_value = self.task_queue_fail_mock
        with self.assertRaises(AnsibleHostsUnavailableError):
            UpdateHardwareInventoryTask().run(self)

    @mock.patch('shared.ansible_tasks.TaskQueueManager')
    def test_get_inventory_data_returns_ansible_facts(self, manager_mock):
        """
        Simulate Ansible Runner facts gathering on a machine.
        """
        manager_mock.return_value = self.task_queue_success_mock
        facts = {'ansible_architecture': 'x86_64'}
        response = UpdateHardwareInventoryTask().run(self)
        self.assertEqual(response, facts)


class AnsiblePlaybookValidationTestCase(TestCase):
    """
    Test cases to test Ansible validation.
    """
    def setUp(self):
        """
        A setup sequence that is built for every test case.
        """
        self.ip = '127.0.0.1'

    def test_ansible_playbook_raises_when_node_is_unreachable(self):
        """
        Test Ansible validation when a host is unreachable.
        """
        stats = mock.MagicMock()
        stats.dark = {self.ip: 1}
        with self.assertRaises(AnsibleHostsUnavailableError):
            AnsiblePlaybookTask.validate(stats)

    def test_ansible_playbook_raises_when_task_failed(self):
        """
        Test Ansible validation when a task has failed.
        """
        stats = mock.MagicMock()
        stats.dark = []
        stats.failures = {self.ip: 1}
        with self.assertRaises(AnsiblePlaybookError):
            AnsiblePlaybookTask.validate(stats)


class AnsiblePlaybookTestCase(TestCase):
    """
    Test cases to test Ansible runner.
    """
    def setUp(self):
        """
        A setup sequence that is built for every test case.
        """
        self.runner = _AnsibleTask()
        self.ip = '10.40.0.10'
        self.populate()

        self.executor = mock.MagicMock()
        self.executor.run = mock.MagicMock(return_value=3)

    @classmethod
    @mock.patch('fabric.models.models_physicalnetworks.ConfigureDHCPTask')
    def setUpTestData(cls, configure_dhcp_mock):
        call_command(
            'loadconfiguration',
            file='api/tests/test_configuration',
            testing=True
        )

    @mock.patch('fabric.models.models_nodes.UpdateHardwareInventoryTask')
    def populate(self, mock_hardware_inventory):
        """
        Populate the database with initial data.
        """
        # sample network
        with mock.patch('fabric.models.models_physicalnetworks'
                        '.ConfigureDHCPTask'):
            self.sample_network = PhysicalNetwork.objects.create(
                name='compute-test-network',
                subnet="10.40.0.0",
                gateway='10.40.0.1',
                prefix=24,
                range_start='10.40.0.10',
                range_end='10.40.0.40'
            )

        facts1 = HardwareInventory.objects.create(inventory='{"cpu": 4}')
        facts2 = HardwareInventory.objects.create(inventory='{"cpu": 4}')
        facts3 = HardwareInventory.objects.create(inventory='{"cpu": 4}')
        # compute01
        self.compute01 = Node.objects.create(
            ip_address="10.40.0.10",
            network=self.sample_network,
            last_boot=datetime.now(),
            active=True,
            node_type=Node.COMPUTE,
            hardware_inventory=facts1
        )

        # compute02 (inactive)
        self.compute02 = Node.objects.create(
            ip_address="10.40.0.11",
            network=self.sample_network,
            last_boot=datetime.now(),
            active=False,
            node_type=Node.COMPUTE,
            hardware_inventory=facts2,
            mac_address='aa:bb:cc:aa:bb:cc'
        )

        # compute03
        self.compute03 = Node.objects.create(
            ip_address="10.40.0.12",
            network=self.sample_network,
            last_boot=datetime.now(),
            active=True,
            node_type=Node.COMPUTE,
            hardware_inventory=facts3,
            mac_address='11:22:33:11:22:33'
        )

        self.sample_cluster = CEPHCluster.objects.create(
            name='test-cluster-01',
            cephx=False,
            fsid='5acff144-de18-4a0e-8fd5-1d8dfc50ceb7',
            mon_host='10.10.10.10',
            username='test-user',
            password='password'
        )

    @mock.patch('shared.ansible_tasks.PlaybookExecutor')
    def test_configure_dhcp_calls_playbook_with_correct_interfaces(
            self, playbook_mock):
        """
        Simulate a dhcp configuration with the correct interfaces.
        """
        ConfigureDHCPTask()([self.sample_network])

        networks = playbook_mock.call_args[1]['variable_manager'].extra_vars['dynamic'][
            'networks']

        self.assertEqual(len(networks), 1)

        network = networks[self.sample_network.subnet]

        self.assertEqual(network['subnet'], self.sample_network.subnet)
        self.assertEqual(network['netmask'], self.sample_network.netmask)
        self.assertEqual(network['gateway'], self.sample_network.gateway)
        self.assertEqual(network['first_address'],
                         self.sample_network.range_start)
        self.assertEqual(network['last_address'],
                         self.sample_network.range_end)

        servers = network['servers']

        self.assertEqual(len(servers), 2)

        node1 = servers[self.compute01.hostname]
        node2 = servers[self.compute03.hostname]

        self.assertEqual(node1['hostname'], self.compute01.hostname)
        self.assertEqual(node1['ip_address'], self.compute01.ip_address)
        self.assertEqual(node1['mac_address'], self.compute01.mac_address)

        self.assertEqual(node2['hostname'], self.compute03.hostname)
        self.assertEqual(node2['ip_address'], self.compute03.ip_address)
        self.assertEqual(node2['mac_address'], self.compute03.mac_address)

        self.assertEqual(playbook_mock.call_count, 1)

    @mock.patch('fabric.models.models_nodes.UpdateHardwareInventoryTask.delay')
    @mock.patch('shared.ansible_tasks.PlaybookExecutor')
    def test_configure_compute_calls_ansible(
            self,
            playbook_mock,
            mock_hardware_inventory):
        """
        Simulate OpenStack configuration mechanism triggered by Ansible.
        """
        playbook_mock.return_value = self.executor

        ceph_cluster = CEPHCluster.objects.first()
        ConfigureComputeTask()(self.ip, ceph_cluster)

        self.assertEqual(playbook_mock.call_count, 1)


class ValidatorTestCase(TestCase):
    def setUp(self):
        self.mac = '01:FF:45:AB:89:ab'
        self.invalid_mac = '01-23-45-67-89-abt'

        self.invalid_ip = '127.0.0.ss1'

        self.ipv4_network = '10.10.0.0'
        self.invalid_ipv4_network = '127.10.0.1'
        self.prefix = 24

        self.vlan = 30
        self.invalid_vlan = 504030

        self.contained_values = [1, 2, 3, 5]
        self.contained_value = self.contained_values[2]

        self.non_contained_values = [0, 4, 6, -50, 44213]
        self.non_contained_value = self.non_contained_values[2]

        self.ipv4 = '10.10.0.0'
        self.invalid_ipv4 = '10.10.04577.0'

        self.node_type = 'compute'
        self.invalid_node_type = 'bengt_node'

    # ValidationAggregator
    def test_validation_aggregator_aggregates_exceptions(self):
        validator = ValidationAggregator(
            mac_address=(validate_mac_address, self.invalid_mac),
            ipv4=(validate_ipv4_address, self.invalid_ip))

        error = None
        try:
            validator.validate()
        except serializers.ValidationError as e:
            error = e

        self.assertIsNotNone(error)
        self.assertEqual(len(error.detail.items()), 2)

    # Mac
    def test_is_mac_allows_mac(self):
        ValidationAggregator(
            mac_address=(validate_mac_address, self.mac)
        ).validate()
        validate_mac_address(self.mac)

    def test_is_mac_raises_on_non_mac(self):
        validator = ValidationAggregator(
            mac_address=(validate_mac_address, self.invalid_mac))

        with self.assertRaises(serializers.ValidationError):
            validator.validate()

    # Ipv4 network
    def test_is_ipv4_network_allows_correct_networks(self):
        ValidationAggregator(
            network=(validate_ipv4_network, self.ipv4_network, self.prefix))\
            .validate()

    def test_is_ipv4_network_raises_on_non_network(self):
        validator = ValidationAggregator(
            network=(validate_ipv4_network,
                     self.invalid_ipv4_network,
                     self.prefix)
        )
        with self.assertRaises(serializers.ValidationError):
            validator.validate()

    # ContainedIn
    def test_contained_in_allows_contained_values(self):
        ValidationAggregator(
            value=(ContainedIn(self.contained_values), self.contained_value))\
            .validate()
        ContainedIn(self.contained_values)(self.contained_value)

    def test_contained_in_raises_on_non_contained_values(self):
        for value in self.non_contained_values:
            with self.assertRaises(serializers.ValidationError):
                ContainedIn(self.contained_values)(value)

    # Node Type
    def test_is_node_type_raises_on_non_node_type(self):
        validator = ValidationAggregator(
            node_type=(IsNodeType(), self.invalid_node_type))
        with self.assertRaises(serializers.ValidationError):
            validator.validate()

    def test_is_node_type_allows_correct_node_types(self):
        ValidationAggregator(node_type=(IsNodeType(), self.node_type))\
            .validate()

    def test_not_contained_allows_non_contained_items(self):
        contained = ContainedIn(self.contained_values)
        Not(contained, '{0} must be unique.')(self.non_contained_value)

    def test_not_contained_disallows_contained_items(self):
        contained = ContainedIn(self.contained_values)
        with self.assertRaises(serializers.ValidationError):
            Not(contained, '{0} must be unique.')(self.contained_value)

    def test_validate_ssh_key_rest_raises_on_bad_key(self):
        validator = IsSSHKey()
        with self.assertRaises(serializers.ValidationError):
            validator("asdasd")

    def test_validate_ssh_key_raises_on_bad_key(self):
        with self.assertRaises(InvalidSSHKeyError):
            validate_ssh_key("asdasd")


class RollbacksTestCase(UnitTestCase):
    def setUp(self):
        self.func1 = mock.MagicMock()
        self.func2 = mock.MagicMock()
        self.func3 = mock.MagicMock()

    def test_all_rollbacks_are_called_on_error(self):
        try:
            with Rollbacks(self.func1, self.func2, self.func3):
                raise Exception
        except:
            pass
        self.func1.assert_any_call()
        self.func2.assert_any_call()
        self.func3.assert_any_call()

    def test_no_rollbacks_are_called_on_success(self):
        with Rollbacks(self.func1, self.func2, self.func3):
            pass
        self.func1.assert_not_called()
        self.func2.assert_not_called()
        self.func3.assert_not_called()
