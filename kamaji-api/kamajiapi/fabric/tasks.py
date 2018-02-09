# -*- coding: utf-8 -*-
import json
import logging
import os
import time

from django.conf import settings

from api import celery_app
import fabric.models
from shared.ansible_tasks import AnsibleRunnerTask, AnsiblePlaybookTask
from shared.exceptions import KamajiOpenStackError
from shared.itertools_extended import roundrobin_perpetual

logger = logging.getLogger(__name__)


class UpdateHardwareInventoryTask(AnsibleRunnerTask):
    """
    Celery task to gather hardware inventory data from servers and update
    add it to a separate table in the database and updates the calling
    models one-to-one relation.
    """
    def run(self, server):
        """
        Run the ansible task to gater the data

        :param server: The server object needs to have an ip_address member
        :type server: fabric.models.Controller or fabric.models.Node
        :return: The fetched ansible facts about the server
        :rtype: dict
        """
        return self.execute(
            'setup',
            server.ip_address,
            become=False
        )[server.ip_address]

    def on_success(self, retval, task_id, (server,), kwargs):
        """
        Create a new HardwareInventory record and update the calling object
        with the relation to the record
        """
        if server.hardware_inventory is None:
            hardware_inventory = \
                fabric.models.HardwareInventory.objects.create(
                    inventory=json.dumps(retval)
                )
            server.hardware_inventory = hardware_inventory
            server.save(do_inventory_update=False)

        else:
            server.hardware_inventory.inventory = json.dumps(retval)
            server.hardware_inventory.save()


class ConfigureNTPServersTask(AnsiblePlaybookTask):
    """
    Task to configure NTP on computes, service nodes and instances.
    """

    def __call__(self, ntp_instance):
        """
        Configure all Computes, ServiceNodes and Instances with the specified
        NTP servers.

        :param ntp_servers: The ntp servers to apply described as a list of
        strings.
        :type ntp_servers: list
        :return: The fetched Ansible facts for the node.
        :rtype: dict
        """
        ntp_urls = fabric.models.NTPSetting.objects.values_list(
            'address',
            flat=True
        )

        extra_vars = {
            'ntp_servers': ntp_urls,
            'ntp_driftfile': '/var/lib/ntp/drift',
            'ntp_restrict': [
                '-4 default kod nomodify notrap nopeer noquery',
                '-6 default kod nomodify notrap nopeer noquery',
                '127.0.0.1',
                '::1'
            ]
        }

        return self.execute(
            os.path.join(settings.ANSIBLE_PATH, 'ntp.yml'),
            extra_vars,
            hosts=fabric.models.Controller.active.get_addresses()
        )

    def run(self, ntp_instance):
        """
        Configure all Computes, ServiceNodes and Instances with the specified
        NTP servers.
        :param ntp: NTP setting object containing info about ntp.
        :type ntp: NTPSetting
        :param ntp_servers: The ntp servers to apply described as a list of
        strings.
        :type ntp_servers: list
        :param args:
        :param kwargs:
        :return:
        """
        logger.info('Starting task to configure ntp servers')
        return self(ntp_instance)

    def on_success(self, retval, task_id, args, kwargs):
        NTPSetting = fabric.models.NTPSetting
        NTPSetting.set_all_statuses(NTPSetting.ACTIVE)
        ntp_urls = NTPSetting.objects.values_list('address', flat=True)
        logger.info('Successfully configured ntp servers: %s.', ntp_urls)

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        NTPSetting = fabric.models.NTPSetting
        NTPSetting.set_all_statuses(NTPSetting.INTERNAL_ERROR)
        ntp_urls = NTPSetting.objects.values_list('address', flat=True)
        logger.info('Failed to configure ntp servers: %s.', ntp_urls)


class ConfigureCephTask(AnsiblePlaybookTask):
    """
    Celery task to configure OpenStack to use CEPH as storage backend
    """
    ignore_result = False

    def __call__(self, ceph_cluster):
        # Create shorthands for commonly used models
        setting = fabric.models.Setting
        credential = fabric.models.Credential

        hosts = fabric.models.Controller.active.get_addresses('osc')
        storage_backend = 'ceph'
        service_domain = setting.objects.get(setting='DomainSetting').domain
        ceph_pool = ceph_cluster.pools.all()
        cinder_db_cred = credential.get_credential(credential.CINDER_DB)
        glance_db_cred = credential.get_credential(credential.GLANCE_DB)
        cinder_cred = credential.get_credential(credential.CINDER)
        glance_cred = credential.get_credential(credential.GLANCE)
        rabbitmq_cred = credential.get_credential(
            credential.RABBITMQ_OPENSTACK)

        extra_vars = {
            'dynamic': {
                'service_domain': service_domain,
                'storage': storage_backend,
                'cluster_name': ceph_cluster.name,
                'uuid': ceph_cluster.uuid,
                'cephx': ceph_cluster.cephx,
                'cinder': {
                    'username': cinder_cred.username,
                    'password': cinder_cred.password,
                },
                'glance': {
                    'username': glance_cred.username,
                    'password': glance_cred.password,
                },
                'rabbitmq': {
                    'username': rabbitmq_cred.username,
                    'password': rabbitmq_cred.password,
                },
                'database': {
                    'cinder': {
                        'username': cinder_db_cred.username,
                        'password': cinder_db_cred.password,
                    },
                    'glance': {
                        'username': glance_db_cred.username,
                        'password': glance_db_cred.password,
                    },
                },
                'config': ceph_cluster.to_config_format(),
                'pools': {obj.type: obj.pool for obj in ceph_pool},
                'credentials': {
                    'username': ceph_cluster.username,
                    'password': ceph_cluster.password
                }
            }
        }

        self.execute(
            os.path.join(settings.ANSIBLE_PATH, 'osc_storage.yml'),
            extra_vars,
            hosts
        )

    def run(self, ceph_cluster):
        """
        :param ceph_cluster: The CEPHCluster object to configure.
        :type ceph_cluster: fabric.models.CEPHCluster
        """
        return self(ceph_cluster)

    def on_success(self, retval, task_id, args, kwargs):
        """
        Update the CEPHCluster object if the Celery task succeed.

        :param args: The CEPHCluster object that is being manipulated on
        :return: None
        """
        cluster = args[0]
        cluster.status = cluster.CONNECTION_CONNECTED
        cluster.save(update_fields=['status'])

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """
        Update the CEPHCluster object if the Celery task fails.

        :param args: The CEPHCluster object that is being manipulated on
        :return: None
        """
        cluster = args[0]
        cluster.status = cluster.CONNECTION_ERROR
        cluster.save(update_fields=['status'])


class ConfigureDHCPTask(AnsiblePlaybookTask):
    """
    Celery task to configure dhcp servers with Ansible.
    """
    def __call__(self, networks):
        """
        Configure the DHCP server on the two hosts with the network
        configuration from the API.
        """

        Host = fabric.models.Host
        Controller = fabric.models.Controller
        hosts = Controller.active.get_addresses('boot')
        # Use a sorted list of our nameservers
        nameservers = Controller.active.get_addresses('ns')
        api_url = 'http://{0}'.format(
            Host.objects.get(type='vip').ip_address
        )
        service_domain = fabric.models.Setting.objects.get(
            setting='DomainSetting').domain

        # We need to create a subnet in the DHCP configuration for our
        # controller network so the second controller node can be PXE booted
        # with the installation image.
        controller02 = Host.objects.get(type='controller', index=2).ip_address

        network_dict = {}
        for network in networks:
            # Get interfaces for all active configured nodes
            nodes = fabric.models.Node.objects.filter(
                network=network,
                active=True
            )

            servers = {
                node.hostname: {
                    'hostname': node.hostname,
                    'ip_address': node.ip_address,
                    'mac_address': node.mac_address
                } for node in nodes
            }

            network_dict[network.subnet] = {
                'subnet': network.subnet,
                'netmask': network.netmask,
                'gateway': network.gateway,
                'first_address': network.range_start,
                'last_address': network.range_end,
                'network_type': network.type,
                'servers': servers
            }

        extra_vars = {
            'dynamic': {
                'api_url': api_url,
                'networks': network_dict,
                'nameservers': nameservers,
                'service_domain': service_domain,
                'second_controller': controller02,
                'server_count': len(hosts)
            }
        }

        return self.execute(
            os.path.join(settings.ANSIBLE_PATH, 'dhcpd.yml'),
            extra_vars,
            hosts
        )

    def run(self, compute_network):
        """
        :param compute_network: The compute network to configure the dhcp with.
        :type compute_network: fabric.models.ComputeNetwork
        """
        return self(compute_network)


class ConfigureComputeTask(AnsiblePlaybookTask):
    """
    Celery task to configure OpenStack on computes with Ansible.
    """

    def __call__(self, node_ip, ceph_cluster):
        """
        Configure OpenStack components (nova, neutron) on a compute node.

        :param node_ip: The address of the node to connect to.
        :type node_ip: str
        :param ceph_cluster: A ceph cluster object
        :type ceph_cluster: CEPHCluster
        """
        # Define shorthands for commonly used models
        Host = fabric.models.Host
        Credential = fabric.models.Credential
        Node = fabric.models.Node

        hosts = [node_ip]
        node = Node.objects.get(ip_address=node_ip)
        self.set_node_state(node_ip, Node.CONVERTING)

        service_domain = fabric.models.Setting.objects.get(
            setting='DomainSetting').domain
        nova_cred = Credential.get_credential(Credential.NOVA)
        neutron_cred = Credential.get_credential(
            Credential.NEUTRON)
        rabbitmq_cred = Credential.get_credential(
            Credential.RABBITMQ_OPENSTACK)
        vip_address = Host.objects.get(type='vip').ip_address
        metadata_secret = Credential.get_credential(
            Credential.OPENSTACK_METADATA_SECRET
        )

        ceph_pool = ceph_cluster.pools.all()

        extra_vars = {
            'dynamic': {
                'service_domain': service_domain,
                'metadata_secret': metadata_secret.password,
                'cluster_name': ceph_cluster.name,
                'uuid': ceph_cluster.uuid,
                'cephx': ceph_cluster.cephx,
                'pools': {obj.type: obj.pool for obj in ceph_pool},
                'config': ceph_cluster.to_config_format(),
                'credentials': {
                    'username': ceph_cluster.username,
                    'password': ceph_cluster.password
                },
                'nova': {
                    'username': nova_cred.username,
                    'password': nova_cred.password,
                },
                'neutron': {
                    'username': neutron_cred.username,
                    'password': neutron_cred.password,
                },
                'rabbitmq': {
                    'username': rabbitmq_cred.username,
                    'password': rabbitmq_cred.password,
                },
                'vip_address': vip_address,
                'hostname': node.hostname,
            }
        }

        self.execute(
            os.path.join(settings.ANSIBLE_PATH, 'compute.yml'),
            extra_vars,
            hosts
        )

    @staticmethod
    def set_node_state(node_ip, new_state):
        node = fabric.models.Node.objects.get(ip_address=node_ip)
        node.state = new_state
        node.save(update_fields='state')

    def on_success(self, retval, task_id, args, kwargs):
        """
        In case the Compute configuration is successful, set the node status
        to created.
        """
        node_ip = args[0]
        ConfigureComputeTask.set_node_state(node_ip, fabric.models.Node.READY)

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """
        In case the Compute configuration fails, set the node status
        to failed.
        """
        node_ip = args[0]
        ConfigureComputeTask.set_node_state(node_ip, fabric.models.Node.FAILED)

    def run(self, ip_address):
        """
        :param ip_address: The ip address to execute the task on.
        :type ip_address: str
        """

        return self(ip_address)


class UploadImageDataFromUrlTask(celery_app.Task):
    """
    Task to download an image file and PUT it to the OpenStack image service.
    """
    POLLING_INTERVAL_SEC = 20

    def run(self, image_id, image_class, *args, **kwargs):
        """
        Prepare the image file data.

        Should be called like:
        delay(image.id, Image)

        :param image_id: The id of the image to prepare.
        :param image_class: The Image class.
        """
        image = image_class.objects.get(id=image_id)
        image.prepare_image_data()

        # If this task is executed twice in a short timespan the second task
        # might find the image to be in 'saving' state and shouldn't return
        # until it is active.
        while image.status == image_class.STATUS_SAVING:
            logger.log('Waiting for image %s to become active.', image_id)
            time.sleep(self.POLLING_INTERVAL_SEC)
            image = image_class.objects.get(id=image_id)

        # If the image upload fails, either in this task instance or another,
        # we should mark the task as failed.
        if image.status == image_class.STATUS_ERROR:
            raise KamajiOpenStackError(
                'Image %s returned error status.', image_id)

        return image_id


class DeployInstanceTask(AnsiblePlaybookTask):
    """
    Task to create instance(s) in OpenStack with help of Kamaji API.
    """

    polling_time = 5
    playbook = 'fabric/ansible/initialize_vm.yml'

    def run(self,
            group_id=None,
            instance=None,
            instance_data=None,
            instances_to_create=None):
        """
        :param instance_data: All data needed to create an instance.
        :type instance_data: dict
        :param instances_to_create: The number of instances to create.
        :type instances_to_create: int
        :param group_id: The group to create the instance in.
        :type group_id: int
        :param instance: Instance to work with, in case one is already created
        :type instance: fabric.models.Instance

        :return: The public ip address of the instance and a service object
        :rtype: Tuple
        """
        from provisioning.models import ServiceGroup

        if instance is None and \
                (instance_data is None or instances_to_create is None):
            raise AttributeError('Either an existing instance or '
                                 'instance_data plus instances_to_create'
                                 'must be specified.')

        if group_id is not None:
            group = ServiceGroup.objects.get(id=group_id)
        else:
            group = None

        instances = []
        if instance:
            if group is not None:
                group.add_instance(instance)

            instances = [instance]
        else:
            from user_management.models import Project
            from fabric.models import (
                Zone, Instance, Image, Flavor, OverlayNetwork
            )

            zone_options = []
            instance_zone_options = instance_data.pop('zone_options')
            for zone in Zone.objects.all():
                if zone.id in instance_zone_options:
                    zone_options.append(zone)

            rr_zones = roundrobin_perpetual(zone_options)
            instance_name = instance_data.pop('name')

            project = Project.objects.get(id=instance_data.pop('project_id'))
            flavor = Flavor.objects.get(id=instance_data.pop('flavor_id'))
            image = Image.objects.get(id=instance_data.pop('image_id'))
            network = OverlayNetwork.objects.get(
                id=instance_data.pop('network_id')
            )

            for index, zone in zip(range(instances_to_create), rr_zones):
                instance = Instance.objects.create(
                    name='{0}{1}'.format(instance_name, index),
                    zone_preferred=zone,
                    zone_options=zone_options,
                    project=project,
                    flavor=flavor,
                    image=image,
                    network=network,
                    **instance_data
                )
                instances.append(instance)

                if group is not None:
                    group.add_instance(instance)

        instance_ips = []
        for instance in instances:
            instance.wait_until_online()
            instance_ips.append(instance.public_ip)

        # Initialize the instances
        self.execute(
            DeployInstanceTask.playbook,
            {},
            instance_ips,
            settings.PROVISIONING_KEY,
            'ubuntu'
        )

        return instance_ips, group_id
