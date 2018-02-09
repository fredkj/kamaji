# -*- coding: utf-8 -*-
from django.core.exceptions import ValidationError
from django.db import models
from django.utils.encoding import python_2_unicode_compatible
from netaddr import IPAddress, IPNetwork

import fabric.models
from fabric.tasks import ConfigureDHCPTask
from fabric.validators import validate_single_controller_network
from shared.exceptions import ResourceInUseError, UnsupportedOperation
from shared.managers import FilteredManager
from shared.models import KamajiModel
from shared.rest_validators import (
    validate_ipv4_network, validate_address_in_network
)


@python_2_unicode_compatible
class PhysicalNetwork(KamajiModel):
    """
    There are two different types of physical networks in Kamaji, one for
    :class:`Compute` and one for :class:`Controller`.
    Starting a :class:`Node` on a compute network will allow it to be configured
    as a :class:`Compute`.
    """

    CONTROLLER_NETWORK = 'controller_network'
    COMPUTE_NETWORK = 'compute_network'
    TYPES = (
        (CONTROLLER_NETWORK, CONTROLLER_NETWORK),
        (COMPUTE_NETWORK, COMPUTE_NETWORK),
    )

    objects = models.Manager()
    controller_networks = FilteredManager({'type': CONTROLLER_NETWORK})

    name = models.CharField(
        max_length=50,
        unique=True,
        help_text='The human readable name of this physical network'
    )
    subnet = models.GenericIPAddressField(
        protocol='IPv4',
        unique=True,
        help_text='The subnet address of this physical network.'
    )
    prefix = models.IntegerField(
        help_text='The subnet prefix of the physical network'
    )
    gateway = models.GenericIPAddressField(
        protocol='IPv4',
        unique=True,
        help_text='The gateway address of this physical network'
    )
    range_start = models.GenericIPAddressField(
        protocol='IPv4',
        unique=True,
        help_text='The first address in this physical network range',
        blank=True,
        null=True
    )
    range_end = models.GenericIPAddressField(
        protocol='IPv4',
        unique=True,
        help_text='The last address in this physical network range',
        blank=True,
        null=True
    )

    type = models.CharField(
        max_length=20,
        choices=TYPES,
        default=COMPUTE_NETWORK,
        help_text='The type of this network.',
        validators=[validate_single_controller_network]
    )

    class Meta:
        app_label = 'fabric'

    def __init__(self, *args, **kwargs):
        self.__ip_network_instance = None
        super(PhysicalNetwork, self).__init__(*args, **kwargs)

    def validate(self):
        """
        Validates that the values for the ip range and gateway are sane.
        If no range is specified we define our own.
        """
        # list of addresses to validate
        network_addresses = [self.gateway]

        if self.range_start and self.range_end:
            network_addresses.append(self.range_start)
            network_addresses.append(self.range_end)
        elif not self.range_start and not self.range_end:
            # If neither range start not end is defined, we define our own
            try:
                default_start, default_end = PhysicalNetwork.get_range(
                    self.subnet,
                    self.prefix,
                    self.gateway
                )
                network_addresses.append(default_start)
                self.range_start = str(default_start)

                network_addresses.append(default_end)
                self.range_end = str(default_end)

            except ValueError as e:
                # get_range throws errors safe to display to the user.
                raise ValidationError(e.message)

        elif not self.range_start:
            raise ValidationError(
                {'range_start': 'Must be specified together with range_end.'})
        else:
            raise ValidationError(
                {'range_end': 'Must be specified together with range_start.'})

        try:
            # Validate that all addresses are in the network
            validate_address_in_network(
                self.subnet,
                self.prefix,
                *network_addresses
            )
        except ValidationError as e:
            raise ValidationError({
                'subnet': e.message,
                'prefix': e.message
            })

        gateway = IPAddress(self.gateway)
        range_start = IPAddress(self.range_start)
        range_end = IPAddress(self.range_end)
        if range_start <= gateway <= range_end:
            raise ValidationError({
                'gateway': 'Ip must be outside of range {0} - {1}.'.format(
                    range_start,
                    range_end)
            })

        try:
            validate_ipv4_network(self.subnet, self.prefix)
        except ValidationError as e:
            raise ValidationError({
                'subnet': e.message,
                'prefix': e.message
            })

        if range_start > range_end:
            detail = 'Range start has to be a lower address than range end.'
            raise ValidationError({
                'range_start': detail,
                'range_end': detail
            })

        super(PhysicalNetwork, self).validate()

    def save(self, **kwargs):
        super(PhysicalNetwork, self).save(**kwargs)
        ConfigureDHCPTask().delay(PhysicalNetwork.objects.all())

    def delete(self, **kwargs):
        network_has_nodes = any(
            [IPAddress(node.ip_address) in self.__ip_network
             for node in fabric.models.Node.objects.all()]
        )

        if network_has_nodes:
            raise ResourceInUseError('Physical network has attached nodes '
                                     'and can\'t be removed')

        # We are not allowed to remove a controller network
        if self.type == self.CONTROLLER_NETWORK:
            raise UnsupportedOperation(
                'A controller network cannot be removed'
            )

        super(PhysicalNetwork, self).delete(**kwargs)

    @property
    def __ip_network(self):
        if self.__ip_network_instance is None:
            self.__ip_network_instance = IPNetwork('{}/{}'.format(
                self.subnet,
                self.prefix)
            )

        return self.__ip_network_instance

    @property
    def netmask(self):
        """The netmask of the network, represented as a string."""
        return str(self.__ip_network.netmask)

    def __str__(self):
        return 'Network: {0}/{1}'.format(self.subnet, self.prefix)

    def __repr__(self):
        return "<{0}: '{1}/{2}' object at {3}>".format(
            self.__class__.__name__,
            self.subnet,
            self.prefix,
            hex(id(self))
        )

    @staticmethod
    def get_range(subnet, prefix, gateway):
        """
        Get the first and last valid address in the IP range that does not
        conflict with the gateway.
        """
        network = IPNetwork('{0}/{1}'.format(subnet, prefix))
        gateway_ip = IPAddress(gateway)
        if network[1] != gateway_ip and network[-2] != gateway_ip:
            raise ValueError(
                'Gateway must be specified as the first or last ip '
                'in the subnet.'
            )

        subnets = list(network)
        subnets.remove(gateway_ip)
        return subnets[1], subnets[-2]
