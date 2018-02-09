# -*- coding: utf-8 -*-
from django.conf.urls import url

from fabric.views import (
    ComputeList, ComputeSingle, FabricLinksList, NodeList,
    NodeSingle, PhysicalNetworkList, PhysicalNetworkSingle,
    SettingSingle, SettingsList, ZoneSingle, ZoneList, PublicKeySingle,
    CEPHClusterList, CEPHClusterSingle, SharesPerTargetList,
    CEPHClusterAction, SMTPRelayAction, NTPAction, StorageSharesList,
    StorageTargetList, NodeHardwareInventory, ExternalStorageMenu,
    StorageShareSingle, StorageTargetRedirect, VolumeList, VolumeSingle,
    ControllerList, ControllerSingle, NTPSettingList, NTPSettingSingle
)

from shared.views import ReducedKwargsRedirectView

fabric_patterns = [
    url(r'^fabric/$',
        FabricLinksList.as_view(),
        name='fabric-root'
    ),
    url(r'^fabric/nodes/$',
        NodeList.as_view(),
        name='nodes'
    ),
    url(r'^fabric/nodes/(?P<mac_address>([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2})/$',
        NodeSingle.as_view(),
        name='node'
    ),
    url(r'^fabric/computes/$',
        ComputeList.as_view(),
        name='computes'
    ),
    url(r'^fabric/computes/(?P<id>[\d]+)/$',
        ComputeSingle.as_view(),
        name='compute'
    ),
    url(
        r'^fabric/nodes/(?P<mac_address>([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2})'
        r'/hardware/$',
        NodeHardwareInventory.as_view(),
        name='node_hardware'
    ),
    url(r'^projects/(?P<project_id>[a-zA-Z0-9-]+)/volumes/$',
        VolumeList.as_view(),
        name='volumes'
    ),
    url(r'^projects/(?P<project_id>[a-zA-Z0-9-]+)/volumes/'
        '(?P<id>[a-zA-Z0-9-]+)/$',
        VolumeSingle.as_view(),
        name='volume'
    ),
    url(r'^fabric/controllers/$',
        ControllerList.as_view(),
        name="controllers"
    ),
    url(r'^fabric/controllers/(?P<id>[\d]+)/$',
        ControllerSingle.as_view(),
        name="controller"
    ),
    url(r'^fabric/physicalnetworks/$',
        PhysicalNetworkList.as_view(),
        name='physicalnetworks'
    ),
    url(r'^fabric/physicalnetworks/(?P<id>[0-9]+)/$',
        PhysicalNetworkSingle.as_view(),
        name='physicalnetwork'
    ),
    url(r'^fabric/settings/PublicKey/$',
        PublicKeySingle.as_view(),
        name='publickey'
    ),
    url(r'^fabric/settings/$',
        SettingsList.as_view(),
        name='settings'
    ),
    url(
        r'^fabric/settings/NTPSetting/$',
        NTPSettingList.as_view(),
        name='ntp_settings'
    ),
    url(
        r'^fabric/settings/NTPSetting/(?P<id>[0-9]+)/$',
        NTPSettingSingle.as_view(),
        name='ntp_setting'
    ),
    url(r'^fabric/settings/(?P<setting>[a-zA-Z]+)/$',
        SettingSingle.as_view(),
        name='setting'
    ),
    url(r'^fabric/settings/NTPSetting/action/$',
        NTPAction.as_view(),
        name='ntp_action'
    ),
    url(
        r'fabric/settings/SMTPRelaySetting/action/$',
        SMTPRelayAction.as_view(),
        name='smtp_relay_action'
    ),
    url(r'^fabric/zones/$',
        ZoneList.as_view(),
        name='zones'
    ),
    url(r'^fabric/zones/(?P<id>[a-zA-Z0-9-]+)/$',
        ZoneSingle.as_view(),
        name='zone'
    ),
    url(r'^fabric/zones/(?P<zone_id>[a-zA-Z0-9-]+)/computes',
        ComputeList.as_view(),
        name='zone_computes'
    ),
    url(r'^fabric/external_storage/$',
        ExternalStorageMenu.as_view(),
        name='external_storage_root'
    ),
    url(r'^fabric/external_storage/ceph/$',
        CEPHClusterList.as_view(),
        name="ceph_targets"
    ),
    url(r'^fabric/external_storage/ceph/(?P<name>[a-zA-Z0-9-_]+)/action/$',
        CEPHClusterAction.as_view(),
        name='ceph_cluster_action'
        ),
    url(r'^fabric/external_storage/shares/$',
        StorageSharesList.as_view(),
        name='storage_shares'
    ),
    url(r'^fabric/external_storage/shares/(?P<name>[a-zA-Z0-9-_]+)/$',
        StorageShareSingle.as_view(),
        name='storage_share'
    ),
    url(r'^fabric/external_storage/targets/$',
        StorageTargetList.as_view(),
        name='storage_targets'
    ),
    url(r'^fabric/external_storage/targets/(?P<name>[a-zA-Z0-9_-]+)/$',
        StorageTargetRedirect.as_view(),
        name='storage_target'
    ),
    url(r'^fabric/external_storage/(?P<backend>[a-z]+)/'
        r'(?P<name>[a-zA-Z0-9_-]+)/shares/$',
        SharesPerTargetList.as_view(),
        name='shares_per_target'
    ),
    url(
        r'^fabric/external_storage/ceph/(?P<target>[a-zA-Z0-9_-]+)/shares/'
        r'(?P<name>[a-zA-Z0-9_-]+)/$',
        ReducedKwargsRedirectView.as_view(
            pattern_name='storage_share',
            permanent=True,
            use_kwargs=('name', )
        )
    ),
    url(r'^fabric/external_storage/(?P<backend>[a-z]+)/'
        r'(?P<name>[a-zA-Z0-9_-]+)/$',
        CEPHClusterSingle.as_view(),
        name="ceph_target"
    )
]

urlpatterns = fabric_patterns
