# -*- coding: utf-8 -*-
import logging

from django.core import exceptions as django_exceptions
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone
from django.utils.encoding import python_2_unicode_compatible

from fabric.models.models_hosts import Host
from fabric.models.models_physicalnetworks import PhysicalNetwork
from fabric.models.models_storage import CEPHCluster
from fabric.tasks import (
    ConfigureDHCPTask, ConfigureComputeTask, UpdateHardwareInventoryTask
)
from shared.exceptions import (
    IncorrectSetupApiException, KamajiApiBadRequest,
    UpdatesNotSupported
)
from shared.models import KamajiModel
from shared.openstack2 import (
    OSModel, RemoteField, OSResourceShortcut
)
from shared.openstack2.fields import RemoteCharField
from shared.openstack2.manager import (
    OpenStackSynchronizingManager, OpenStackManager
)

logger = logging.getLogger(__name__)


def get_node_index():
    return Node.objects.count() + 1


class HardwareInventory(models.Model):
    """
    Stores the hardware inventory of a node in JSON format.
    """
    inventory = models.TextField(
        help_text='Contains the Hardware inventory in Json format'
    )

    class Meta:
        app_label = 'fabric'


@python_2_unicode_compatible
class Node(models.Model):
    """
    Stores a node that can be configured as a compute.
    """
    UNCONFIGURED = 'unconfigured'
    COMPUTE = 'compute'
    NODE_TYPES = (
        (UNCONFIGURED, UNCONFIGURED),
        (COMPUTE, COMPUTE),
    )

    READY = 'READY'
    FAILED = 'FAILED'
    CONVERTING = 'CONVERTING'
    STATE_TYPES = (
        (READY, READY),
        (FAILED, FAILED),
        (CONVERTING, CONVERTING),
    )

    ip_address = models.GenericIPAddressField(
        protocol='IPv4',
        unique=True,
        help_text='The allocated IP address of this node'
    )

    mac_address = models.CharField(
        max_length=20,
        help_text='The MAC address of this node',
        primary_key=True
    )

    network = models.ForeignKey(PhysicalNetwork)

    last_boot = models.DateTimeField(
        auto_now_add=True,
        help_text='The date and time when this node was last seen'
    )

    active = models.BooleanField(
        default=True,
        help_text='True if node is active else false'
    )

    node_type = models.CharField(
        max_length=20,
        choices=NODE_TYPES,
        default=UNCONFIGURED,
        help_text='The type of this node'
    )

    hardware_inventory = models.OneToOneField(
        HardwareInventory,
        on_delete=models.SET_DEFAULT,
        null=True,
        default=None
    )

    revision = models.IntegerField(default=1, help_text='Current revision')

    state = models.CharField(
        max_length=20,
        null=True,
        choices=STATE_TYPES,
        help_text='Current state of this node',
        default=READY
    )

    index = models.IntegerField(
        help_text='The index of this node',
        default=get_node_index,
        unique=True
    )

    @property
    def hostname(self):
        """
        :return: The hostname by combining "node" and this nodes index padded to two digits.
        """
        return 'node{0:02d}'.format(self.index)

    def save(self, update_fields=None, do_inventory_update=True, **kwargs):
        # Only perform the node_type reconfiguration if that field is relevant
        # for the save operation.
        if update_fields is None or 'node_type' in update_fields:
            try:
                # Try to get an existing object, if this save is an update
                existing_object = self.__class__.objects.get(pk=self.pk)
                current_type = existing_object.node_type

                # Get the CEPHCluster object
                ceph_cluster = CEPHCluster.objects.first()

                # Only perform the save operation if the type field has changed
                if current_type != self.node_type:
                    if self.node_type == self.COMPUTE:
                        if not CEPHCluster.objects.exists():
                            raise IncorrectSetupApiException(
                                'External storage must be configured before '
                                'compute nodes can be added'
                            )
                        (
                            ConfigureDHCPTask().si(
                                PhysicalNetwork.objects.all()) |
                            ConfigureComputeTask().si(
                               self.ip_address,
                               ceph_cluster
                            )
                        ).apply_async()

                elif self.node_type == self.COMPUTE:
                    ConfigureComputeTask().delay(
                        self.ip_address,
                        ceph_cluster
                    )

                # In case the state variable is changed since this method
                # started executing (i.e. the Ansible tasks are running
                # synchronously, update it from the db to avoid overwriting it
                self.refresh_from_db(fields=['state'])

            except self.__class__.DoesNotExist:
                # If the object is not present it should be created so an
                # empty except is ok here
                pass

        self.revision += 1
        self.last_boot = timezone.now()
        super(Node, self).save(**kwargs)

        # Avoid infinite recursion can, since ConfigureComputeTask also calls the
        # save method but with update_fields='state'.
        if do_inventory_update and update_fields is None:
            UpdateHardwareInventoryTask().delay(self)

    def delete(self, *args, **kwargs):
        if self.hardware_inventory is not None:
            self.hardware_inventory.delete()
        super(Node, self).delete(*args, **kwargs)

    class Meta:
        app_label = 'fabric'

    def __str__(self):
        return 'Node: {0}, Mac: {1}, Revision: {2}'.format(self.hostname,
                                                           self.mac_address,
                                                           self.revision)

    def __repr__(self):
        return "<{0}: '{1}' object at {2}>".format(self.__class__.__name__,
                                                   self.mac_address,
                                                   hex(id(self)))


class Compute(OSModel):
    """
    Stores information about a hypervisor in OpenStack.
    """
    # The length is constrained so our dns names won't be too long
    hostname = RemoteCharField(max_length=126, source='hypervisor_hostname')
    status = RemoteField()
    state = RemoteField()
    version = RemoteField(source='hypervisor_version')
    host_ip = RemoteField()
    free_disk_gb = RemoteField()
    free_ram_mb = RemoteField()
    vcpus = RemoteField()
    vcpus_used = RemoteField()
    local_gb_used = RemoteField()
    memory_mb = RemoteField()
    memory_mb_used = RemoteField()
    running_vms = RemoteField()
    current_workload = RemoteField()

    objects = OpenStackManager()
    synced_objects = OpenStackSynchronizingManager()

    class OpenStackMeta:
        service = 'compute'
        resource = 'os-hypervisors'

    @property
    def _openstack_resource_label(self):
        return 'hypervisor'

    @property
    def zone(self):
        try:
            return self.zone_mapping.zone
        except ZoneComputesMapping.DoesNotExist:
            return None

    @zone.setter
    def zone(self, zone):
        try:
            self.zone_mapping.delete()
        except ZoneComputesMapping.DoesNotExist:
            # The compute had no zone, which is fine.
            pass

        if zone is not None:
            zone.computes_mapping.create(compute=self)

    @zone.deleter
    def zone(self):
        try:
            self.zone_mapping.delete()
        except ZoneComputesMapping.DoesNotExist:
            # The compute had no zone, which is fine.
            pass

    @property
    def node(self):
        index = self.hostname.lstrip("node")
        return Node.objects.get(index=index)

    def __hash__(self):
        """
        Calculate a hash value for this compute based on it's id and host name,
        asserting that two equal objects will render the same hash value.
        This is used when performing set operations with computes, primarily in
        the Zone model.

        :return: A hashed value based on the id and hostname of the compute
        :rtype: int
        """
        return hash(str(self.openstack_id) + str(self.hostname))

    def __eq__(self, other):
        """
        Determine whether this Compute and some other object are equal.
        Computes can only be equal with objects of the same type. If the
        object passed to the method is of any other type, the method will
        return false.

        Equality between two Compute object is determined by assessing that the
        id field is equal.

        :param other: The object to compare this Compute to.
        :type other: object
        :return: Whether this Compute and the other object are equal.
        :rtype: bool
        """
        if isinstance(other, Compute):
            return (other.openstack_id == self.openstack_id
                    and other.hostname == self.hostname)

        return False

    def __repr__(self):
        return "<{0}: '{1}' object at {2}>".format(
            self.__class__.__name__,
            self.hostname,
            hex(id(self))
        )

    def __str__(self):
        return 'Name: {0}'.format(self.hostname)

    def save(self, **kwargs):
        if self.is_created:
            raise UpdatesNotSupported

        super(Compute, self).save(**kwargs)


class Controller(KamajiModel):
    """
    Stores information about controller nodes.
    The brain of your openstack cluster. it contains all central OpenStack components
    such as databases, openstack controller software (keystone, nova etc).
    """
    SINGLE = 'single'
    READY_TO_JOIN = 'ready_to_join_cluster'
    CLUSTERED = 'clustered'
    STATUSES = (
        (SINGLE, SINGLE),
        (READY_TO_JOIN, READY_TO_JOIN),
        (CLUSTERED, CLUSTERED),
    )

    name = models.CharField(
        max_length=100,
        unique=True,
        help_text='Name of this node'
    )

    primary = models.BooleanField(
        default=False,
        help_text='Indicates if this controller is primary in environment'
    )

    ip_address = models.GenericIPAddressField(
        protocol='IPv4',
        unique=True,
        help_text='The allocated IP address of this node'
    )

    hardware_inventory = models.OneToOneField(
        HardwareInventory,
        on_delete=models.SET_DEFAULT,
        null=True,
        default=None,
        blank=True
    )

    status = models.CharField(
        max_length=25,
        choices=STATUSES,
        default=READY_TO_JOIN,
        help_text='The status of this controller.'
    )

    class ActivesManager(models.Manager):
        def get_queryset(self):
            """
            Get a list of all active controllers.
            :return: The QuerySet of all active controllers.
            :rtype: QuerySet
            """
            objects = super(Controller.ActivesManager, self).get_queryset()
            singles = objects.filter(status=Controller.SINGLE)
            if singles.exists():
                return singles
            else:
                return objects.filter(status=Controller.CLUSTERED)

        def get_addresses(self, *host_types):
            """
            Get all addresses for the specified host types.
            :param host_types: The host types to filter the result by.
            :type host_types: *str
            :return: List of ip_addresses
            :rtype: list
            """
            addresses = []
            for active in self.get_queryset():
                host_maps = active.host_map.filter(host__type__in=host_types)
                for host_map in host_maps:
                    addresses.append(host_map.host.ip_address)
            return addresses

    objects = models.Manager()
    active = ActivesManager()

    def validate(self):
        # Make sure that we don't create more controllers than we support
        if not self.is_created and Controller.objects.count() >= 2:
            raise django_exceptions.ValidationError(
                'Maximum number of controllers already exists'
            )

        # Only allow one controller to be primary
        if self.primary:
            primary_controllers = self.__class__.objects.filter(primary=True)

            if self.is_created:
                primary_controllers = primary_controllers.exclude(pk=self.pk)

            if primary_controllers.exists():
                raise django_exceptions.ValidationError({
                    'primary': 'Only one controller in the cluster can be set '
                               'as primary'
                })

        super(Controller, self).validate()

    def save(self, do_inventory_update=True, *args, **kwargs):
        is_creating = not self.is_created

        if is_creating and self.primary:
            self.status = Controller.SINGLE

        super(Controller, self).save(*args, **kwargs)

        if is_creating:
            controller_index = 1 if self.primary else 2

            # Populate the mapping controller -> host
            for host in Host.objects.filter(index=controller_index):
                self.host_map.create(host=host)

        if do_inventory_update:
            UpdateHardwareInventoryTask().delay(self)

    def delete(self, *args, **kwargs):
        if self.hardware_inventory is not None:
            self.hardware_inventory.delete()
        super(Controller, self).delete(*args, **kwargs)

    class Meta:
        app_label = 'fabric'


class ControllerHostMapping(models.Model):
    """
    This model maps a number of :class:`fabric.models.models_hosts.Host` to a :class:`Controller`.
    """
    controller = models.ForeignKey(Controller, related_name='host_map')
    host = models.OneToOneField(Host, related_name='controller_map')


class Zone(OSModel):
    """
    Represents a Kamaji Zone (i.e. failure domain) mapped to an os-aggregate in OpenStack.
    """
    name = RemoteField(unique=True)
    _availability_zone = RemoteField(
        source='availability_zone',
        target='availability_zone'
    )
    updated_at = RemoteField(read_only=True)
    created_at = RemoteField(read_only=True)

    @property
    def computes(self):
        return [mapping.compute for mapping in self.computes_mapping.all()]

    @computes.setter
    def computes(self, computes):
        """
        Sets the computes for this zone.
        :raises: ValidationError
        """
        for mapping in self.computes_mapping.exclude(compute__in=computes):
            mapping.delete()

        errors = []
        message_template = '{0} is already in a zone.'
        for compute in computes:
            try:
                self.computes_mapping.get_or_create(compute=compute)
            except ValidationError:
                errors.append(
                    ValidationError(message_template.format(compute.hostname))
                )

        if len(errors) > 0:
            raise ValidationError({'computes': errors})

    class OpenStackMeta:
        service = 'compute'
        resource = 'os-aggregates'

    @property
    def _openstack_resource_label(self):
        return 'aggregate'

    def __str__(self):
        return '<{0}: {1}>'.format(
            self.__class__.__name__,
            self.name
        )

    def __repr__(self):
        return "<{0}: '{1}' object at {2}>".format(
            self.__class__.__name__,
            self.name,
            hex(id(self))
        )

    def validate(self):
        errors = []
        message_template = '{0} is already assigned to zone {1}.'
        for compute in self.computes:
            if compute.zone is not None and compute.zone != self:
                errors.append(message_template.format(
                    compute.hostname,
                    compute.zone.name
                ))

        if len(errors) > 0:
            raise ValidationError({'computes': errors})

        super(Zone, self).validate()

    def save(self, **kwargs):
        # Set the name as the availability_zone as we don't need to
        # separate the two
        self._availability_zone = self.name

        super(Zone, self).save(**kwargs)

    def delete(self):
        if len(self.computes) > 0:
            raise KamajiApiBadRequest("Can't remove zone <{0}> since it has "
                                      "assigned computes.".format(self.name))
        if len(self.instances) > 0:
            raise KamajiApiBadRequest("Can't remove zone <{0}> since it has "
                                      "assigned instances.".format(self.name))

        super(Zone, self).delete()


class ZoneComputesMapping(KamajiModel):
    """
    A mapping of a :class:`Zone` to a :class:`Compute`.
    """
    zone = models.ForeignKey(
        Zone,
        models.CASCADE,
        related_name='computes_mapping'
    )
    compute = models.OneToOneField(
        Compute,
        models.CASCADE,
        related_name='zone_mapping'
    )

    class Meta:
        unique_together = ('zone', 'compute')

    def __str__(self):
        return '<{0} for Zone: {1} and Compute: {2}>'.format(
            self.__class__.__name__,
            self.zone,
            self.compute
        )

    def __repr__(self):
        return '<{0}: Zone: {1} <-> Compute: {2} object at {3}>'.format(
            self.__class__.__name__,
            self.zone.name,
            self.compute,
            hex(id(self))
        )

    def save(self, **kwargs):
        # Trigger the validation pre-save to validate uniqueness.
        self.validate()

        OSResourceShortcut(
            Zone.OpenStackMeta.service,
            Zone.OpenStackMeta.resource,
            path=(self.zone.openstack_id, 'action')
        ).post(json={'add_host': {'host': self.compute.hostname}})

        super(ZoneComputesMapping, self).save(
            perform_validation=False,
            **kwargs
        )

    def delete(self, **kwargs):
        OSResourceShortcut(
            Zone.OpenStackMeta.service,
            Zone.OpenStackMeta.resource,
            path=(self.zone.openstack_id, 'action')
        ).post(json={'remove_host': {'host': self.compute.hostname}})

        super(ZoneComputesMapping, self).delete(**kwargs)
