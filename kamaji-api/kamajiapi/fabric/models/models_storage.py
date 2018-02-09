# -*- coding: utf-8 -*-
import logging
import rados
import uuid

from tempfile import NamedTemporaryFile

from jinja2 import Template
from django.db import models
from django.conf import settings
from django.utils.encoding import python_2_unicode_compatible

from fabric.tasks import ConfigureCephTask

logger = logging.getLogger(__name__)


def generate_uuid():
    """
    Generate a random UUID.
    :return: Randomly generated UUID
    :rtype: string
    """
    return str(uuid.uuid4())


class StorageTarget(models.Model):
    """
    Base class for any Storage class.
    """
    class Meta:
        abstract = True


class CEPHCluster(StorageTarget):
    """
    Represents a connection to a CEPH cluster that are used for image storage.
    """
    CONNECTION_DISCONNECTED = 'disconnected'
    CONNECTION_CONNECTING = 'connecting'
    CONNECTION_CONNECTED = 'connected'
    CONNECTION_ERROR = 'error'

    CONNECTION_STATUSES = (
        (CONNECTION_DISCONNECTED, CONNECTION_DISCONNECTED),
        (CONNECTION_CONNECTING, CONNECTION_CONNECTING),
        (CONNECTION_CONNECTED, CONNECTION_CONNECTED),
        (CONNECTION_ERROR, CONNECTION_ERROR)
    )

    name = models.CharField(max_length=255,
                            primary_key=True,
                            help_text='A local identifier for the cluster')
    cephx = models.BooleanField(help_text='Whether the cluster uses CEPHx')
    uuid = models.UUIDField(default=generate_uuid,
                            help_text='A generated UUID used by libvirt')
    fsid = models.UUIDField(help_text='The fsid of the cluster')
    mon_host = models.GenericIPAddressField(help_text='The monitor config host'
                                                      ' of the cluster')
    status = models.CharField(
        max_length=127,
        choices=CONNECTION_STATUSES,
        default=CONNECTION_DISCONNECTED,
        help_text='The connection status of the cluster '
                  '(disconnected/connecting/connected/error)'
    )
    username = models.CharField(max_length=255,
                                help_text='The username to use when Kamaji is '
                                          'authenticating against the cluster')
    password = models.CharField(max_length=255,
                                help_text='The password to use when Kamaji is '
                                          'authenticating against the cluster')

    class Meta:
        app_label = 'fabric'

    def __str__(self):
        return 'Name: {0}, UUID: {1}, Status: {2}'.format(self.name,
                                                          self.uuid,
                                                          self.status)

    def __repr__(self):
        return "<{0}: '{1}' object at {2}>".format(self.__class__.__name__,
                                                   self.name,
                                                   hex(id(self)))

    def connect(self):
        """
        Create a connection to the storage backend using the data in the
        instance.
        """
        self.status = self.CONNECTION_CONNECTING
        self.save(update_fields=('status',))
        ceph_task = ConfigureCephTask()
        ceph_task.delay(self)

    def to_config_format(self):
        """
        Export the CEPH cluster configuration to config file format for use
        together with Ansible.

        :return: The cluster connection configuration in config file format.
        :rtype: str
        """
        config_template = "[global]\n" \
                          "fsid = {{ fsid }}\n" \
                          "mon_host = {{ mon_host }}\n" \
                          "{% if cephx == True %}" \
                          "auth_cluster_required = cephx\n" \
                          "auth_service_required = cephx\n" \
                          "auth_client_required = cephx\n" \
                          "{% endif %}"
        config = Template(config_template)
        return config.render(fsid=self.fsid,
                             mon_host=self.mon_host,
                             cephx=self.cephx)

    def test_connection(self):
        """
        Tests the connection to the ceph cluster.
        """
        with self._keyring(self.username, self.password) as keyring:
            cluster = rados.Rados(
                conf={
                    'mon_host': str(self.mon_host),
                    'keyring': keyring.path}
            )

            try:
                cluster.connect(timeout=settings.CONNECTION_TEST_TIMEOUT)
                return {'status': cluster.state}
            except rados.InterruptedOrTimeoutError as e:
                logger.exception(e.message)
                return {'status': self.CONNECTION_ERROR,
                        'message': e.message}
            except rados.Error as e:
                logger.exception(e.message)
                return {'status': self.CONNECTION_ERROR,
                        'message': 'error connecting to the cluster'}

    class _keyring(object):
        """
        Context manager that creates a temporary ceph keyring file and removes
        it once the execution leaves the context.
        """

        def __init__(self, username, password):
            self.username = username
            self.password = password

        def __enter__(self):
            self.tmp_file = NamedTemporaryFile(mode='w', bufsize=0)
            self.__write_keyring(self.tmp_file, self.username, self.password)
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            self.tmp_file.close()

        @staticmethod
        def __write_keyring(keyring_file, username, password):
            """
            Writes keyring info in a config file format to the file.
            """
            keyring_file.write('[client.{0}]\n'.format(username))
            keyring_file.write('\tkey = {0}\n'.format(password))

        @property
        def path(self):
            if self.tmp_file:
                return self.tmp_file.name
            else:
                raise Exception("The tmp file must be opened before accessing "
                                "it's path.")


@python_2_unicode_compatible
class CEPHClusterPool(models.Model):
    """
    Represents a CEPH cluster pool.
    """
    POOL_TYPE_VOLUME = 'volume'
    POOL_TYPE_IMAGE = 'image'
    POOL_TYPE_META = 'meta'
    POOL_TYPES = (
        (POOL_TYPE_VOLUME, POOL_TYPE_VOLUME),
        (POOL_TYPE_IMAGE, POOL_TYPE_IMAGE),
        (POOL_TYPE_META, POOL_TYPE_META)
    )

    cluster = models.ForeignKey(CEPHCluster,
                                related_name='pools',
                                help_text='The CEPH cluster to tie this pool '
                                          'to')
    pool = models.CharField(max_length=255,
                            help_text='The CEPH cluster pool identifier')
    type = models.CharField(max_length=127,
                            choices=POOL_TYPES,
                            unique=True,
                            help_text='The type of data to store in this pool '
                                      '(volume/image/meta). Only one pool '
                                      ' per type is allowed.')

    class Meta:
        app_label = 'fabric'

    def __str__(self):
        return 'Pool: {0}, Type: {1}'.format(self.pool, self.type)

    def __repr__(self):
        return "<{0}: '{1}' object at {2}>".format(self.__class__.__name__,
                                                   self.pool,
                                                   hex(id(self)))
