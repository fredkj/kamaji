# -*- coding: utf-8 -*-
import logging
import socket
from collections import OrderedDict
from smtplib import SMTPServerDisconnected

from django import http
from django.core.mail import send_mail
from django.http import Http404
from rest_framework import permissions
from rest_framework.generics import (
    RetrieveAPIView, RetrieveUpdateDestroyAPIView, ListAPIView, ListCreateAPIView, RetrieveUpdateAPIView
)
from rest_framework.response import Response
from rest_framework.reverse import reverse
from rest_framework.views import APIView

from fabric.models import (
    Node, PhysicalNetwork, Compute, Zone, Setting, NTPSetting, SSHKey, CEPHCluster,
    CEPHClusterPool, Controller, HardwareInventory
)
from fabric.serializers import (
    ComputeSerializer, NodeSerializer, NodePatchSerializer,
    ZoneSerializer,
    PublicKeySerializer, CEPHClusterSerializer, CEPHClusterPoolSerializer,
    StorageShareSerializer, ControllerSerializer, HardwareInventorySerializer,
    PhysicalNetworkSerializer, NTPSettingSerializer, SettingSerializer
)
from shared.openstack2 import NotFoundError
from shared.openstack2 import OSResourceShortcut
from shared.views import ActionView
from shared.views import LookupMixin
from user_management.models import Project

logger = logging.getLogger(__name__)


class FabricLinksList(APIView):
    """ Available endpoints under Fabric """
    def get(self, request, *attr):
        return Response(OrderedDict(
            [('computes_link', reverse('computes', request=request)),
             ('external_storage_root_link', reverse(
                 'external_storage_root', request=request)
              ),
             ('controllers_link', reverse('controllers', request=request)),
             ('physical_networks_link', reverse(
                 'physicalnetworks', request=request)
              ),
             ('nodes_link', reverse('nodes', request=request)),
             ('settings_link', reverse('settings', request=request)),
             ('zones_link', reverse('zones', request=request))]
        ))


class NodeList(ListCreateAPIView):
    """
    List and create Nodes.

    Called when a compute nodes has booted up.

    .. note:: Changes in unregistered node IP's are handled.
    """

    # Disable the permission system as this method is called by an
    # unregistered node that has no access to credentials of any kind.
    permission_classes = (
        permissions.AllowAny,
    )

    queryset = Node.objects.all()
    serializer_class = NodeSerializer


class NodeSingle(RetrieveUpdateAPIView):
    """
    Lookup or update a specific Node.
    """
    # Disable the permission system as this method is called by an
    # unregistered node that has no access to credentials of any kind.
    permission_classes = (
        permissions.AllowAny,
    )

    queryset = Node.objects.all()
    lookup_url_kwarg = 'mac_address'

    def get_serializer_class(self):
        if self.request.method == 'GET':
            return NodeSerializer
        else:
            return NodePatchSerializer


class NodeHardwareInventory(RetrieveAPIView):
    serializer_class = HardwareInventorySerializer

    def get_object(self, *args, **kwargs):
        try:
            node = Node.objects.get(**self.kwargs)
            return node.hardware_inventory
        except (Node.DoesNotExist, HardwareInventory.DoesNotExist):
            raise Http404


class ComputeList(ListAPIView):
    """
    List all existing compute nodes.
    """
    serializer_class = ComputeSerializer

    def get_queryset(self):
        if self.kwargs and 'zone_id' in self.kwargs:
            zone = Zone.objects.get(id=self.kwargs['zone_id'])
            return zone.computes

        return Compute.synced_objects.all()


class ComputeSingle(RetrieveUpdateAPIView):
    """
    Retrieve or update a specific compute node.
    """
    serializer_class = ComputeSerializer
    queryset = Compute.objects.all()
    lookup_field = 'id'


class ControllerList(ListCreateAPIView):
    """
    List or create controllers.
    """
    serializer_class = ControllerSerializer
    queryset = Controller.objects.all()


class ControllerSingle(RetrieveUpdateDestroyAPIView):
    """
    Retrieve or delete a specific controller.
    """
    serializer_class = ControllerSerializer
    lookup_field = 'id'
    queryset = Controller.objects.all()


class PhysicalNetworkList(ListCreateAPIView):
    """
    Create or list compute networks.
    """
    serializer_class = PhysicalNetworkSerializer
    queryset = PhysicalNetwork.objects.all()


class PhysicalNetworkSingle(RetrieveUpdateDestroyAPIView):
    """
    Retrieve, update or remove a compute network.
    """
    serializer_class = PhysicalNetworkSerializer
    queryset = PhysicalNetwork.objects.all()
    lookup_field = 'id'


class NTPAction(ActionView):
    """
    Allows testing the configured NTP servers.
    The test is performed by posting an JSON object on the
    form {'action': 'test'}
    """

    @ActionView.action
    def test(self):
        """
        Execute a connection test to the listed NTP servers in Kamaji settings
        and update their status.
        """
        response = {}
        for ntp in NTPSetting.objects.all():
            response[ntp.address] = ntp.test()
        return response


class SMTPRelayAction(ActionView):
    """
    Allows testing the configured SMTP settings.
    The test is performed by posting an JSON object on the form
    {'action': 'test', 'recipient': 'your@mail.com'}
    """

    TEST_MAIL_SUBJECT = 'Kamaji SMTP Test'
    TEST_MAIL_CONTENT = (
        'Congratulations!\n\n'
        'Since you have received this mail, it means that you have '
        'successfully configured SMTP for your Kamaji installation.\n'
    )

    @ActionView.action
    def test(self, recipient):
        """
        Test sending an email to verify that SMTP settings are correctly
        configured
        """
        try:
            send_mail(
                SMTPRelayAction.TEST_MAIL_SUBJECT,
                SMTPRelayAction.TEST_MAIL_CONTENT,
                'noreply@kamaji.io',
                (recipient,)
            )
        except (socket.error, SMTPServerDisconnected):
            return {
                'result': 'fail',
                'error': 'Failed sending message through specified SMTP relay'
            }

        return {'result': 'success'}


class SettingsList(APIView):
    """
    List links to all available settings in Kamaji.
    """

    def get(self, request, format=None):
        base_url = reverse('settings', request=request)

        settings_links = {
            '{0}_link'.format(setting.setting): '{0}{1}/'.format(
                base_url,
                 setting.setting
            )
            for setting in Setting.objects.all()
        }

        settings_links['NTPSetting_link'] = reverse(
            'ntp_settings',
            request=request
        )

        return Response(settings_links)


class SettingSingle(RetrieveUpdateAPIView):
    """
    Retrieve or update a specific setting in Kamaji.
    """
    lookup_field = 'setting'
    queryset = Setting.objects.all()

    def get_serializer_class(self, *args, **kwargs):
        return SettingSerializer.get_dedicated_serializer(
            self.kwargs['setting']
        )


class NTPSettingList(ListCreateAPIView):
    serializer_class = NTPSettingSerializer
    queryset = NTPSetting.objects.all()


class NTPSettingSingle(RetrieveUpdateDestroyAPIView):
    serializer_class = NTPSettingSerializer
    queryset = NTPSetting.objects.all()
    lookup_field = 'id'


class ZoneList(ListCreateAPIView):
    """
    List or create new zones in the Kamaji cloud.
    """
    serializer_class = ZoneSerializer
    queryset = Zone.objects.all()


class ZoneSingle(RetrieveUpdateDestroyAPIView):
    """
    Retrieve, update or remove an existing zone in the Kamaji cloud.
    """
    serializer_class = ZoneSerializer
    lookup_field = 'id'
    queryset = Zone.objects.all()

    def get_serializer_context(self):
        context = super(ZoneSingle, self).get_serializer_context()
        context['id'] = self.kwargs[self.lookup_field]
        return context


class VolumeList(APIView):
    def get(self, request, *args, **kwargs):
        # TODO: Replace this with proper OSModel once we can get a
        # handle on volume resources.
        try:
            project = Project.objects.get(id=kwargs.get('project_id'))
        except Project.DoesNotExist:
            raise Http404

        volumes = OSResourceShortcut(
            'volumev2',
            'volumes',
            project=project.openstack_id,
            path=['detail']
        ).get()
        return Response(volumes)


class VolumeSingle(APIView):
    def get(self, request, *args, **kwargs):
        # TODO: Replace this with proper OSModel once we can get a
        # handle on volume resources.
        try:
            project = Project.objects.get(id=kwargs.get('project_id'))
        except Project.DoesNotExist:
            raise Http404

        try:
            volume = OSResourceShortcut(
                'volumev2',
                'volumes',
                project=project.openstack_id,
                path=[kwargs.get('id')]
            ).get()
            return Response(volume)
        except NotFoundError:
            raise Http404


class PublicKeySingle(RetrieveAPIView):
    """
    Retrieve public key used in Kamaji.
    """
    # Everyone should be allowed to view this.
    permission_classes = (
        permissions.AllowAny,
    )

    def get(self, request, *args, **kwargs):
        queryset = SSHKey.objects.filter(service=SSHKey.KAMAJI_SSH_KEY)
        serializer = PublicKeySerializer(queryset.first())
        return Response(serializer.data)


class ExternalStorageMenu(APIView):
    """
    List available endpoints under external_storage
    """
    def get(self, request, format=None):
        return Response(OrderedDict(
            (
                ('storage_shares_link', reverse('storage_shares',
                                                request=request)),
                ('storage_targets_link', reverse('storage_targets',
                                                 request=request)),
                ('ceph_targets_link', reverse('ceph_targets',
                                              request=request))
            )
        ))


class CEPHClusterList(ListCreateAPIView):
    """
    List existing or create a new connection to a CEPH storage cluster.
    """
    serializer_class = CEPHClusterSerializer
    queryset = CEPHCluster.objects.all()


class CEPHClusterSingle(RetrieveUpdateDestroyAPIView):
    """
    Delete, update or show info about the CEPH cluster connection.
    """
    serializer_class = CEPHClusterSerializer
    lookup_field = 'name'
    queryset = CEPHCluster.objects.all()


class SharesPerTargetList(ListCreateAPIView):
    """
    List the existing pools or create a new pool for the configured CEPH
    cluster.
    """
    lookup_field = 'name'
    serializer_class = CEPHClusterPoolSerializer

    def get_queryset(self):
        try:
            return CEPHCluster.objects.get(**{
                self.lookup_field: self.kwargs[self.lookup_field]}).pools.all()
        except CEPHCluster.DoesNotExist:
            raise Http404


class CEPHClusterAction(ActionView, LookupMixin):
    """
    Provides the possibility to connect and test configured CEPH cluster.
    Connecting a cluster is performed by posting an JSON object on the
    form {'action': 'connect'}.
    Testing a cluster is performed by posting an JSON object on the
    form {'action': 'test'}.
    """
    lookup_field = 'name'
    queryset = CEPHCluster.objects.all()

    @ActionView.action
    def connect(self):
        """
        Setup the connection to the cluster.
        """
        cluster = self.get_object()
        cluster.connect()
        return {'status': cluster.status}

    @ActionView.action
    def test(self):
        """
        Test the connection to the cluster.
        """
        return self.get_object().test_connection()


class StorageTargetList(APIView):
    """
    Fetch all storage targets, serialize them and present them
    in the same endpoint.
    """
    def get(self, request, format=None):
        result = []
        result.extend(CEPHClusterSerializer(
            CEPHCluster.objects.all(),
            many=True,
            context={'request': request}
        ).data)

        # Append additional serialized storage backend to the result

        return Response(result)


class StorageTargetRedirect(RetrieveAPIView):
    """
    Perform a redirect from the targets endpoint to the appropriate
    storage backend endpoint:
    /target/<name> -> /<backend>/<name>/
    """
    queryset = CEPHCluster.objects.all()
    lookup_field = 'name'

    def get(self, *args, **kwargs):
        target = self.get_object()
        url = reverse('ceph_target', kwargs={
            'backend': 'ceph',
            'name': target.name
        })

        return http.HttpResponsePermanentRedirect(url)


class StorageSharesList(ListCreateAPIView):
    """ List and create storage shares """

    serializer_class = StorageShareSerializer
    queryset = CEPHClusterPool.objects.all()


class StorageShareSingle(RetrieveUpdateDestroyAPIView):
    """ Allow retrieval, updates and removal of shares """

    serializer_class = StorageShareSerializer
    queryset = CEPHClusterPool.objects.all()
    lookup_field = 'pool'
    lookup_url_kwarg = 'name'
