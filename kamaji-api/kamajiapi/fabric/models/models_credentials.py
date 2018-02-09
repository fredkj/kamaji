# -*- coding: utf-8 -*-

from django.db import models


class Credential(models.Model):
    """
    Stores a username and password or token tied to a service.
    The items in the SERVICES tuple must match the services added in the
    install process.
    """
    POWERDNS_DB = 'mariadb_powerdns'
    KEYSTONE_DB = 'mariadb_keystone'
    NEUTRON_DB = 'mariadb_neutron'
    KAMAJI_DB = 'mariadb_kamaji'
    CINDER_DB = 'mariadb_cinder'
    GLANCE_DB = 'mariadb_glance'
    NOVA_DB = 'mariadb_nova'
    NEUTRON = 'openstack_neutron'                           # OpenStack
    OPENSTACK_ADMIN = 'openstack_admin'                     # OpenStack Admin API
    CINDER = 'openstack_cinder'                             # OpenStack Block Storage API
    GLANCE = 'openstack_glance'                             # OpenStack Image API
    SWIFT = 'openstack_swift'                               # OpenStack Storage API
    NOVA = 'openstack_nova'                                 # OpenStack Compute API
    OPENSTACK_METADATA_SECRET = 'openstack_metadata_secret'
    OPENSTACK_ADMIN_TOKEN = 'openstack_admin_token'         # OpenStack Admin
    POWERDNS_API_KEY = 'powerdns_api_key'                   # DNS api key
    RABBITMQ_CELERY = 'rabbitmq_celery'
    RABBITMQ_OPENSTACK = 'rabbitmq_openstack'

    # The services Kamaji consists of and need to communicate with.
    SERVICES = (
        (POWERDNS_DB, POWERDNS_DB),
        (KEYSTONE_DB, KEYSTONE_DB),
        (NEUTRON_DB, NEUTRON_DB),
        (KAMAJI_DB,  KAMAJI_DB),
        (CINDER_DB, CINDER_DB),
        (GLANCE_DB, GLANCE_DB),
        (NOVA_DB, NOVA_DB),
        (NEUTRON, NEUTRON),
        (OPENSTACK_ADMIN, OPENSTACK_ADMIN),
        (CINDER, CINDER),
        (GLANCE, GLANCE),
        (SWIFT, SWIFT),
        (NOVA, NOVA),
        (OPENSTACK_METADATA_SECRET, OPENSTACK_METADATA_SECRET),
        (OPENSTACK_ADMIN_TOKEN, OPENSTACK_ADMIN_TOKEN),
        (POWERDNS_API_KEY, POWERDNS_API_KEY),
        (RABBITMQ_CELERY, RABBITMQ_CELERY),
        (RABBITMQ_OPENSTACK, RABBITMQ_OPENSTACK)
    )

    service = models.CharField(max_length=250, choices=SERVICES)
    password = models.CharField(max_length=250)
    username = models.CharField(max_length=250)

    class Meta:
        app_label = 'fabric'

    @staticmethod
    def get_credential(service):
        return Credential.objects.get(service=service)


class SSHKey(models.Model):
    """
    Stores an SSH key tied to a service.
    """
    KAMAJI_SSH_KEY = 'kamaji_ssh_key'   # The public key installed in instances to allow provisioning.

    SERVICES = (
        (KAMAJI_SSH_KEY, KAMAJI_SSH_KEY),
    )

    service = models.CharField(max_length=250, choices=SERVICES)
    key = models.CharField(max_length=2000)

    class Meta:
        app_label = 'fabric'

    def __str__(self):
        return 'Service: {0}, Key: {1}'.format(self.service, self.key)

    def __repr__(self):
        return "<{0}: '{1}' object at {2}>".format(self.__class__.__name__,
                                                   self.service,
                                                   hex(id(self)))
