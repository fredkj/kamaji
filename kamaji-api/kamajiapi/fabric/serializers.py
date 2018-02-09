# -*- coding: utf-8 -*-
import json
import logging
from collections import OrderedDict

from netaddr import IPAddress, IPNetwork
from rest_framework import serializers
from rest_framework.exceptions import MethodNotAllowed
from rest_framework.validators import UniqueValidator

from fabric.models import NTPSetting
from fabric.models import (
    Node, Zone, Setting, Compute, SSHKey, CEPHCluster, CEPHClusterPool,
    PhysicalNetwork, Controller, HardwareInventory
)
from shared.fields import (
    MultipleKeyHyperlinkedRelatedField, StaticRelatedField
)
from shared.rest_validators import (
    is_valid_name,
    validate_network_prefix, validate_mac_address, validate_hostname,
)

logger = logging.getLogger(__name__)


class HardwareInventorySerializer(serializers.ModelSerializer):
    @staticmethod
    def __get_nic_info(nic_data):
        nic_info = OrderedDict((
            ('macaddress', nic_data['macaddress']),
            ('module', nic_data['module']),
            ('mtu', nic_data['mtu']),
            ('active', nic_data['active']),
        ))

        if 'ipv4' in nic_data:
            nic_info['ipv4'] = nic_data['ipv4']

        return nic_info

    @staticmethod
    def __get_partition_info(partition_info):
        return {
            'size': partition_info['size']
        }

    @staticmethod
    def __get_storage_info(storage_data):
        return OrderedDict((
            ('host', storage_data['host']),
            ('size', storage_data['size']),
            ('partitions', {
                key: HardwareInventorySerializer.__get_partition_info(value)
                for key, value in storage_data['partitions'].items()
            })
        ))

    def to_representation(self, instance):
        ret = super(HardwareInventorySerializer, self).to_representation(instance)
        ret.pop('inventory', None)
        if instance.inventory is not None:
            hardware_inventory = json.loads(instance.inventory)

            ret['cpu'] = OrderedDict((
                ('vcpus', hardware_inventory['ansible_processor_vcpus']),
                ('type', ' '.join(hardware_inventory['ansible_processor'][:2]))
            ))

            memory_data = hardware_inventory['ansible_memory_mb']['real']
            ret['memory_mb'] = OrderedDict((
                ('total', memory_data['total']),
                ('free', memory_data['free']),
                ('used', memory_data['used'])
            ))

            ret['nics'] = OrderedDict((
                # Slice at 8 chars to remove 'ansible' from key and
                # leave nic name
                (key[8:], self.__class__.__get_nic_info(value)) for (key, value)
                in hardware_inventory.iteritems()
                if key.startswith('ansible_eth')
            ))

            ret['storage_devices'] = OrderedDict((
                (key, self.__class__.__get_storage_info(value))
                for key, value in hardware_inventory['ansible_devices'].items()
            ))

        return ret

    class Meta:
        model = HardwareInventory
        fields = ('inventory',)


class NodeSerializer(serializers.ModelSerializer):
    network = serializers.PrimaryKeyRelatedField(
        queryset=PhysicalNetwork.objects.all(),
        required=False,
    )
    hardware_link = serializers.HyperlinkedIdentityField(
        view_name='node_hardware',
        lookup_field='mac_address'
    )
    network_link = serializers.HyperlinkedIdentityField(
        view_name='physicalnetwork',
        lookup_field='network_id',
        lookup_url_kwarg='id'
    )
    prefix = serializers.IntegerField(max_value=32, required=False)
    mac_address = serializers.CharField(
        max_length=20,
        validators=[
            UniqueValidator(queryset=Node.objects.all()),
            validate_mac_address
        ]
    )

    class Meta:
        model = Node
        fields = ('hostname',
                  'state',
                  'ip_address',
                  'network',
                  'network_link',
                  'prefix',
                  'last_boot',
                  'node_type',
                  'mac_address',
                  'hardware_link')
        read_only_fields = ('state', 'hardware_inventory')

    def validate(self, values):
        # If network is not specified, try to calculate it from the ip +
        # prefix.
        if 'network' not in values:
            if 'prefix' not in values:
                raise serializers.ValidationError({
                    'network': 'Either network or prefix must be specified'
                })

            subnet = IPNetwork("{0}/{1}".format(
                values['ip_address'],
                values['prefix'])
            ).network

            try:
                network = PhysicalNetwork.objects.get(
                    subnet=str(subnet),
                    prefix=values['prefix']
                )
            except PhysicalNetwork.DoesNotExist:
                raise serializers.ValidationError({
                    'network': 'No configured network for '
                               'ip_address "{0}"'.format(values['ip_address'])
                })

            values['network'] = network

            # Pop the prefix field, to avoid problems when creating a new Node
            # object since the model has no such field
            del values['prefix']

        # Validate that the ip address is within the network range
        range_start = IPAddress(values['network'].range_start)
        range_end = IPAddress(values['network'].range_end)
        node_ip = IPAddress(values['ip_address'])

        if not range_start <= node_ip <= range_end:
            raise serializers.ValidationError({
                'ip_address': 'IP address is not within the network range'
            })

        return super(NodeSerializer, self).validate(values)


class NodePatchSerializer(serializers.ModelSerializer):
    class Meta:
        model = Node
        fields = ['node_type']
        extra_kwargs = {'node_type': {'required': True}}


class ComputeSerializer(serializers.Serializer):
    id = serializers.CharField(
        read_only=True,
        help_text='Id of the compute'
    )
    hostname = serializers.CharField(
        read_only=True,
        help_text='Hostname of the compute'
    )
    status = serializers.CharField(
        read_only=True,
        help_text='The status of the compute'
    )
    state = serializers.CharField(
        read_only=True,
        help_text='The state of the compute'
    )
    zone = serializers.SlugRelatedField(
        slug_field='name',
        queryset=Zone.objects.all(),
        allow_null=True,
        help_text='The zone of the compute.'
    )
    node_link = serializers.HyperlinkedRelatedField(
        view_name='node',
        read_only=True,
        lookup_field='mac_address',
        source='node'
    )

    version = serializers.IntegerField(read_only=True, required=False)
    host_ip = serializers.CharField(read_only=True, required=False)
    free_disk_gb = serializers.IntegerField(read_only=True, required=False)
    free_ram_mb = serializers.IntegerField(read_only=True, required=False)
    vcpus = serializers.IntegerField(read_only=True, required=False)
    vcpus_used = serializers.IntegerField(read_only=True, required=False)
    local_gb = serializers.IntegerField(read_only=True, required=False)
    local_gb_used = serializers.IntegerField(read_only=True, required=False)
    memory_mb = serializers.IntegerField(read_only=True, required=False)
    memory_mb_used = serializers.IntegerField(read_only=True, required=False)
    running_vms = serializers.IntegerField(read_only=True, required=False)
    current_workload = serializers.IntegerField(read_only=True, required=False)

    def update(self, instance, validated_data):
        """
        Only updates the zone. All other attributes are controlled
        by OpenStack.
        """
        if validated_data['zone'] != instance.zone:
            instance.zone = validated_data['zone']

        return instance


class ControllerSerializer(serializers.ModelSerializer):
    hardware_inventory = HardwareInventorySerializer(read_only=True)
    status = serializers.CharField(read_only=True)

    class Meta:
        model = Controller
        fields = (
            'id', 'name', 'primary', 'ip_address', 'status',
            'hardware_inventory'
        )


class PhysicalNetworkSerializer(serializers.ModelSerializer):
    """
    ModelSerializer for the physical network model.
    """
    subnet = serializers.IPAddressField(
        protocol='IPv4',
        validators=[UniqueValidator(queryset=PhysicalNetwork.objects.all())]
    )
    gateway = serializers.IPAddressField(
        protocol='IPv4',
        validators=[UniqueValidator(queryset=PhysicalNetwork.objects.all())]
    )
    range_start = serializers.IPAddressField(protocol='IPv4', required=False)
    range_end = serializers.IPAddressField(protocol='IPv4', required=False)
    prefix = serializers.IntegerField(validators=[validate_network_prefix])

    class Meta:
        model = PhysicalNetwork
        fields = ('id', 'name', 'subnet', 'prefix', 'gateway',
                  'range_start', 'range_end', 'type')


class SettingSerializer(serializers.Serializer):
    """
    Base serializer for all settings.
    """
    @staticmethod
    def get_dedicated_serializer(setting_name):
        """
        Get a dedicated serializer with specific validation and formatting for
        a specific setting.

        :param setting_name: The name of the setting to get a serializer for
        :type setting_name: str
        :return: The dedicated serializer for the given setting
        :rtype: SettingSerializer
        """
        if setting_name == 'ZoneLimitSetting':
            return ZoneLimitSerializer
        elif setting_name == 'ResolverSetting':
            return ResolverSettingSerializer
        elif setting_name == 'DomainSetting':
            return DomainSettingSerializer
        elif setting_name == 'SMTPRelaySetting':
            return SMTPRelaySettingSerializer
        else:
            return GenericSettingSerializer

    def create(self, validated_data):
        raise NotImplementedError

    def update(self, instance, validated_data):
        instance.data = validated_data['data']
        instance.save()
        return instance

    def to_internal_value(self, data):
        ret = super(SettingSerializer, self).to_internal_value(data)
        return {
            'setting': self.instance.setting,
            'data': json.dumps(ret)
        }


class GenericSettingSerializer(serializers.ModelSerializer):

    class Meta:
        model = Setting
        fields = '__all__'


class ZoneLimitSerializer(SettingSerializer):
    zone_limit = serializers.IntegerField()


class ResolverSettingSerializer(SettingSerializer):
    resolvers = serializers.ListField(
        child=serializers.IPAddressField(protocol='IPv4')
    )


class DomainSettingSerializer(SettingSerializer):
    domain = serializers.RegexField(r'^[\.a-zA-Z0-9]+$')

    def update(self, instance, validated_data):
        raise MethodNotAllowed('', detail='Method PUT or PATCH not allowed')


class SMTPRelaySettingSerializer(SettingSerializer):
    connection_security = serializers.ChoiceField(choices=(
        'none', 'ssl', 'tls'
    ))

    smtp_port = serializers.IntegerField(min_value=0, max_value=65535)
    smtp_host = serializers.CharField(validators=(validate_hostname,))

    action_link = StaticRelatedField(
             view_name='smtp_relay_action'
    )


class ZoneSerializer(serializers.Serializer):
    id = serializers.CharField(read_only=True, help_text='The id of the zone')
    name = serializers.CharField(
        max_length=250,
        help_text='Name of the zone',
        validators=[is_valid_name],
        required=True
    )
    updated_at = serializers.CharField(
        read_only=True,
        help_text='The date and time when the zone was updated'
    )
    created_at = serializers.CharField(
        read_only=True,
        help_text='The date and time when the zone was created'
    )
    computes = serializers.SlugRelatedField(
        slug_field='hostname',
        queryset=Compute.objects.all(),
        many=True,
        required=False,
        help_text='List of computes coupled with the zone'
    )
    computes_link = serializers.HyperlinkedIdentityField(
        view_name='zone_computes',
        lookup_field='id',
        lookup_url_kwarg='zone_id'
    )

    def create(self, validated_data):
        zone_limit = int(Setting.objects.get(
            setting='ZoneLimitSetting'
        ).zone_limit)

        if Zone.objects.count() > zone_limit:
            raise serializers.ValidationError(
                "Failed creating the new zone. "
                "Zone limit ({0}) reached.".format(zone_limit)
            )

        computes = validated_data.pop('computes', [])
        created_zone = Zone.objects.create(**validated_data)
        created_zone.save()

        created_zone.computes = computes

        return created_zone

    def update(self, instance, validated_data):
        for field, value in validated_data.items():
            setattr(instance, field, value)
        instance.save()
        return instance

    def to_representation(self, instance):
        ret = super(ZoneSerializer, self).to_representation(instance)
        ret['computes'] = [compute.hostname for compute in instance.computes
                           if hasattr(compute, 'hostname')]
        return ret


class NTPSettingSerializer(serializers.ModelSerializer):
    address = serializers.CharField(validators=(validate_hostname, ))
    action_link = StaticRelatedField(view_name='ntp_action')

    class Meta:
        model = NTPSetting
        fields = (
            'id',
            'address',
            'status',
            'connection_status',
            'last_test',
            'last_test_stratum',
            'action_link'
        )

        read_only_fields = (
            'id',
            'status',
            'connection_status',
            'last_test',
            'last_test_stratum',
            'action_link'
        )


class PublicKeySerializer(serializers.ModelSerializer):
    class Meta:
        model = SSHKey
        fields = ['key']


class CEPHClusterPoolSerializer(serializers.ModelSerializer):
    """
    Serializer for the CEPHClusterPool model. The serializer will attempt to
    extract
    """
    cluster_link = MultipleKeyHyperlinkedRelatedField(
        view_name='ceph_target',
        lookup_field_mapping={
            'name': 'cluster_id'
        },
        static_field_mapping={
            'backend': 'ceph'
        }
    )

    # This line is added to circumvent a bug in Django REST Framework where
    # validators are not picked up by ChoiceFields in ModelSerializers, causing
    # nasty integrity errors in the DB layer.
    type = serializers.ChoiceField(choices=CEPHClusterPool.POOL_TYPES,
                                   validators=[UniqueValidator(
                                       queryset=CEPHClusterPool.objects.all(),
                                       message='This pool type is already '
                                               'configured for this cluster'
                                   )])

    def validate(self, attrs):
        # In case the cluster relationship is not stated in the data, try
        # extracting it from the context kwargs (i.e. url). If not found there
        # raise a validation error.
        if 'cluster_id' not in attrs:
            try:
                cluster = CEPHCluster.objects.get(
                    name=self.context['view'].kwargs['name']
                )

                attrs['cluster'] = cluster
            except KeyError:
                raise serializers.ValidationError(
                    {'cluster_id': 'Missing value'}
                )

        attrs = super(CEPHClusterPoolSerializer, self).validate(attrs)

        return attrs

    class Meta:
        model = CEPHClusterPool
        fields = ['pool', 'type', 'cluster_link']


class CEPHClusterSerializer(serializers.ModelSerializer):
    """
    ModelSerializer for the CEPHCluster model. Currently only allows creation
    of a single CEPHCluster, since Kamaji does not support multiple
    CEPH cluster configurations.
    """
    status = serializers.CharField(read_only=True)
    shares_link = MultipleKeyHyperlinkedRelatedField(
        view_name='shares_per_target',
        lookup_field_mapping={
            'name': 'name',
        },
        static_field_mapping={
            'backend': 'ceph'
        }
    )
    action_link = serializers.HyperlinkedIdentityField(
        view_name='ceph_cluster_action',
        lookup_field='name',
        lookup_url_kwarg='name'
    )

    def create(self, validated_data):
        """
        Create a new CEPHCluster, unless there is already an existing
        configuration. If so, raise validation error.

        :param validated_data: The input data after passing through the
        validation system.
        :type validated_data: dict
        :return: The created instance
        :rtype: CEPHCluster
        """
        if CEPHCluster.objects.count() > 0:
            error = serializers.ValidationError('Kamaji only support a single '
                                                'CEPH cluster')
            error.status_code = 422
            raise error

        return super(CEPHClusterSerializer, self).create(validated_data)

    class Meta:
        model = CEPHCluster
        fields = ('name', 'cephx', 'fsid', 'mon_host', 'status',
                  'username', 'password', 'shares_link', 'action_link')


class StorageShareSerializer(serializers.ModelSerializer):
    name = serializers.CharField(source='pool')
    target = serializers.SlugRelatedField(
        source='cluster',
        slug_field='name',
        queryset=CEPHCluster.objects.all()
    )

    target_link = MultipleKeyHyperlinkedRelatedField(
        view_name='ceph_target',
        lookup_field_mapping={
            'name': 'cluster_id',
        },
        static_field_mapping={
            'backend': 'ceph'
        }
    )

    class Meta:
        model = CEPHClusterPool
        fields = ('name', 'type', 'target', 'target_link')
