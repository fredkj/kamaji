# -*- coding: utf-8 -*-
import re
import string

import netaddr
from django.core import exceptions

from rest_framework import serializers, validators
from sshpubkeys import SSHKey, InvalidKeyException

from shared.exceptions import InvalidSSHKeyError


VALID_NAME_EXTRA_CHARS = '-_'
VALID_NAME_CHARS = set(string.letters + string.digits + VALID_NAME_EXTRA_CHARS)

MUST_BE_UNIQUE_MESSAGE = validators.UniqueValidator.message


def _raise_validation_error(message, field):
    if field is None:
        raise serializers.ValidationError(message)
    else:
        raise serializers.ValidationError({field: message})


class ValidationAggregator(object):
    """
    Allows aggregation of :class:`rest_framework.serializers.ValidationError`,
    if one or more errors are detected the resulting
    :class:`rest_framework.serializers.ValidationError` will contain the
    details of all failed validations.
    """
    def __init__(self, **validations):
        """
        :param validations: Will be treated as a dict on the form:
        {field_name:(validator_function, value1, value2, ...), ...}
        """
        self.validations = validations

    def validate(self):
        """
        Validates all validations and aggregates the exception details into a
        dictionary with the validated fields as keys and error details as
        values.

        :raises: :class:`rest_framework.serializers.ValidationError`
        """
        errors = {}
        for field, validation in self.validations.items():
            try:
                validator = validation[0]
                values = validation[1:]
                validator(*values)
            except serializers.ValidationError as e:
                errors[field] = e.detail
            except exceptions.ValidationError as e:
                errors[field] = e.message
        if len(errors) > 0:
            raise serializers.ValidationError(errors)


class Not(object):
    """
    Inverts a validation.
    Results in a failed validation if the specified validation succeeds
    and vice versa.

    :raises: :class:`rest_framework.serializers.ValidationError`
    """
    def __init__(self, validation, message_template, field=None):
        """
        :param validation: The validation to invert.
        :param message_template: Message to display if the validation fails.
        Will be formatted with the value being validated.
        :param field: The name of the field being validated.
        """
        self.validation = validation
        self.message_template = message_template
        self.field = field

    def __call__(self, value):
        thrown = False
        try:
            self.validation(value)
        except serializers.ValidationError:
            thrown = True
        finally:
            if not thrown:
                message = self.message_template.format(value)
                _raise_validation_error(message, self.field)


class ContainedIn(object):
    """
    Validates that the value exists in the specified list.

    :raises: :class:`rest_framework.serializers.ValidationError`
    """
    def __init__(self, value_list, field=None):
        self.value_list = value_list
        self.format_string = "Must be either of {0}."
        self.field = field

    def __call__(self, value):
        if value not in self.value_list:
            message = self.format_string.format(self.value_list)
            _raise_validation_error(message, self.field)


class IsNodeType(ContainedIn):
    """
    Validates that the value is a valid NodeType.

    :raises: :class:`rest_framework.serializers.ValidationError`
    """
    def __init__(self):
        from fabric.models import Node
        super(IsNodeType, self).__init__([item[0] for item in Node.NODE_TYPES])
        self.format_string = "'{0}' is not a valid node type."


def validate_network_prefix(value):
    """
    Validate a network prefix given as an integer.

    :param value: The network prefix to validate
    :type value: int
    :raises: :class:`rest_framework.serializers.ValidationError`
    """
    if not 1 <= value <= 32:
        message = "'{0}' is not a valid network prefix.".format(value)
        raise serializers.ValidationError(message)


def validate_mac_address(value):
    """
    Validate a Network MAC address given as a string, on the form
    XX:XX:XX:XX:XX:XX

    :param value: The MAC address to validate
    :type value: str
    :raises: :class:`rest_framework.serializers.ValidationError`
    """
    if not re.match("^([0-9a-fA-F]{2}:){5}[0-9a-fA-F]{2}$", value):
        message = "'{0}' is not a valid MAC address.".format(value)
        raise serializers.ValidationError(message)


def validate_vlan_id(value):
    """
    Validate a vlan-id given as an integer.

    :param value: The vlan-id to validate.
    :type value: int
    :raises: :class:`rest_framework.serializers.ValidationError`
    """
    if not 1 <= value <= 4094:
        message = "'{0}' is not a valid vlan id".format(value)
        raise serializers.ValidationError(message)


def validate_ipv4_network_compound(value):
    """
    Validates that the provided value describes a network together with a
    prefix on the form: 10.10.0.0/24.

    :param value: The value to validate.
    :raises: :class:`rest_framework.serializers.ValidationError`
    """
    net = value.split('/')
    if len(net) != 2:
        raise serializers.ValidationError(
            "'{0}' is not a valid IP network.".format(value))
    validate_ipv4_network(*net)


def validate_ipv4_network(subnet, prefix, gateway=None):
    """
    Validates that the subnet and prefix describes a valid IP network
    (ex 10.10.0.0/24).
    If gateway address is specified, check that the IP address is within the
    network range.

    :param subnet: The subnet to validate.
    :param prefix: The prefix to validate.
    :param gateway: The gateway to validate.
    :raises: :class:`rest_framework.serializers.ValidationError`
    """
    try:
        network_object = netaddr.IPNetwork('{0}/{1}'.format(subnet, prefix))
        if network_object.version != 4:
            raise exceptions.ValidationError(
                "'{0}/{1}' is not a valid IPv4 network.".format(subnet,
                                                                prefix)
            )
        if str(network_object.network) != subnet:
            message = "'{0}/{1}' is not a valid subnet/network id".format(
                subnet, prefix)
            raise exceptions.ValidationError(message)
        if gateway:
            gateway_object = netaddr.IPAddress(gateway)
            if gateway_object not in network_object.iter_hosts():
                raise exceptions.ValidationError(
                    "'{0}' is not within the '{1}/{2}' network range".format(
                        str(gateway_object), subnet, prefix))
    except netaddr.AddrFormatError:
        message = "'{0}/{1}' is not a valid IP network.".format(subnet, prefix)
        raise exceptions.ValidationError(message)


def validate_address_in_network(subnet, prefix, *addresses):
    """
    Validate that the address or addresses are in the specified network.

    :param subnet: The network subnet
    :type subnet: string
    :param prefix: The network prefix
    :type prefix: integer
    :param addresses: The address or addresses to validate
    :type addresses: string or list
    :raises: :class:`rest_framework.serializers.ValidationError`
    """
    ip_object = netaddr.IPNetwork('{0}/{1}'.format(subnet, prefix))

    for address in addresses:
        if netaddr.IPAddress(address) not in ip_object.iter_hosts():
            raise exceptions.ValidationError(
                    "'{0}' is not within the '{1}/{2}' network range".format(
                        address, subnet, prefix))


def validate_hostname(value):
    """
    Validate that a hostname is valid.

    :param value: The hostname to validate.
    :type value: str
    :raises: :class:`rest_framework.serializers.ValidationError`
    """

    message = "'{0}' is not a valid hostname.".format(value)

    if len(value) > 255:
        raise serializers.ValidationError(message)

    if value[-1] == ".":
        value = value[:-1]  # strip exactly one dot from the right, if present

    allowed = re.compile("(?!-)[A-Z\d-]{1,63}(?<!-)$", re.IGNORECASE)

    if not all(allowed.match(x) for x in value.split(".")):
        raise serializers.ValidationError(message)


def is_valid_name(text):
    """:raises: :class:`rest_framework.serializers.ValidationError`"""
    if not VALID_NAME_CHARS.issuperset(set(text)):
        raise serializers.ValidationError(
            'Must only contain letters, digits and {0}'
            .format(str(VALID_NAME_EXTRA_CHARS))
        )


def contained_in_dict(field, attrs):
    """
    Validate that a dict contains a specified field

    :param field: The field that must be present in the attrs dict
    :type field: str
    :param attrs: The dict where to search for the field
    :type attrs: dict
    :raises: :class:`rest_framework.serializers.ValidationError`
    """

    if field not in attrs:
        raise serializers.ValidationError({
            field: 'This field is required.'
        })


def validate_ssh_key(key):
    """:raises: :class:`rest_framework.serializers.ValidationError`"""
    ssh = SSHKey(key, strict_mode=True)
    try:
        ssh.parse()
    except InvalidKeyException:
        raise InvalidSSHKeyError
    except NotImplementedError:
        raise InvalidSSHKeyError('Invalid key type')


class IsSSHKey(object):
    """:raises: :class:`rest_framework.serializers.ValidationError`"""
    def __init__(self, allow_blank=False):
        self.allow_blank = allow_blank

    def __call__(self, value):
        if not value:
            if not self.allow_blank:
                raise serializers.ValidationError("Cannot be blank")
        else:
            try:
                validate_ssh_key(value)
            except InvalidSSHKeyError as e:
                raise serializers.ValidationError(e.message)
