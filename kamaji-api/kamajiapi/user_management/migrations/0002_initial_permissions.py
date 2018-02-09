# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import logging

from django.db import migrations

from shared.permission_management import (
    create_permission, create_read_permission, read_permission,
    read_update_delete_permission, read_delete_permission,
    read_update_permission, update_delete_permission
)
from user_management.models import Permission, Role, GlobalGroup

log = logging.getLogger(__name__)


def setup_permissions(apps, schema_editor):
    """ Setup all permissions in the system """
    Permission.create(
        name='kamaji:link:view',
        views=[
            read_permission('APIRootLinksList'),
            read_permission('UserManagementLinksList'),
            read_permission('FabricLinksList'),
            read_permission('CloudLinksList'),
            read_permission('ExternalStorageMenu'),
            read_permission('ProvisioningLinksList')
        ]
    )

    Permission.create(
        name='fabric:externalstorage:manage',
        views=[
            create_read_permission('CEPHClusterList'),
            read_update_delete_permission('CEPHClusterSingle'),
            create_read_permission('SharesPerTargetList'),
            create_permission('CEPHClusterAction'),
            read_permission('StorageTargetList'),
            read_permission('StorageTargetRedirect'),
            create_read_permission('StorageSharesList'),
            read_update_delete_permission('StorageShareSingle')
        ]
    )

    Permission.create(
        name='fabric:ceph:test',
        views=[read_permission('CEPHClusterAction')]
    )

    Permission.create(
        name='fabric:externalstorage:view',
        views=[
            read_permission('CEPHClusterList'),
            read_permission('CEPHClusterSingle'),
            read_permission('SharesPerTargetList'),
            read_permission('CEPHClusterPoolSingle'),
            read_permission('StorageTargetList'),
            read_permission('StorageTargetRedirect'),
            read_permission('StorageSharesList'),
            read_permission('StorageShareSingle')
        ]
    )

    Permission.create(
        name='fabric:compute:view',
        views=[
            read_permission('ComputeList'),
            read_permission('ComputeSingle')
        ]
    )

    Permission.create(
        name='fabric:compute:manage',
        views=[
            create_read_permission('ComputeList'),
            read_update_delete_permission('ComputeSingle')
        ]
    )

    Permission.create(
        name='fabric:controller:view',
        views=[
            read_permission('ControllerList'),
            read_permission('ControllerSingle')
        ]
    )

    Permission.create(
        name='fabric:controller:manage',
        views=[
            create_read_permission('ControllerList'),
            read_update_delete_permission('ControllerSingle')
        ]
    )

    Permission.create(
        name='cloud:flavor:view',
        views=[
            read_permission('FlavorList'),
            read_permission('FlavorSingle')
        ]
    )

    Permission.create(
        name='cloud:flavor:manage',
        views=[
            create_read_permission('FlavorList'),
            read_update_delete_permission('FlavorSingle')
        ]
    )

    Permission.create(
        name='cloud:image:view',
        views=[
            read_permission('ImageList'),
            read_permission('ImageSingle')
        ]
    )

    Permission.create(
        name='cloud:image:manage',
        views=[
            create_read_permission('ImageList'),
            read_update_delete_permission('ImageSingle'),
            create_permission('ImageAction')
        ]
    )

    Permission.create(
        name='cloud:instance:view',
        views=[
            read_permission('InstanceList'),
            read_permission('InstanceSingle'),
            read_permission('InstanceSingle'),
            read_permission('InstanceByProjectList'),
            read_permission('InstanceListReadonly'),
            read_permission('InstanceSingleReadonly')
        ]
    )

    Permission.create(
        name='cloud:instance:manage',
        views=[
            read_permission('InstanceList'),
            read_permission('InstanceSingle'),
            create_read_permission('InstanceByProjectList'),
            read_update_delete_permission('InstanceSingle'),
            read_permission('InstanceListReadonly'),
            read_permission('InstanceSingleReadonly'),
            create_permission('InstanceActionView')
        ]
    )

    Permission.create(
        name='fabric:physicalnetwork:manage',
        views=[
            create_read_permission('PhysicalNetworkList'),
            read_update_delete_permission('PhysicalNetworkSingle')
        ]
    )

    Permission.create(
        name='fabric:physicalnetwork:view',
        views=[
            read_permission('PhysicalNetworkList'),
            read_permission('PhysicalNetworkSingle')
        ]
    )

    Permission.create(
        name='fabric:node:view',
        views=[
            read_permission('NodeList'),
            read_permission('NodeSingle'),
            read_permission('UnconfiguredNodeList'),
            read_permission('NodeHardwareInventory')
        ]
    )

    Permission.create(
        name='fabric:node:manage',
        views=[
            read_permission('NodeList'),
            read_update_delete_permission('NodeSingle'),
            create_read_permission('UnconfiguredNodeList')
        ]
    )

    Permission.create(
        name='cloud:overlaynetwork:view',
        views=[
            read_permission('OverlayNetworkList'),
            read_permission('OverlayNetworkSingle'),
            read_permission('OverlaySubnetList'),
            read_permission('OverlaySubnetSingle')
        ]
    )

    Permission.create(
        name='cloud:overlaynetwork:manage',
        views=[
            create_read_permission('OverlayNetworkList'),
            read_update_delete_permission('OverlayNetworkSingle'),
            create_read_permission('OverlaySubnetList'),
            read_update_delete_permission('OverlaySubnetSingle')
        ]
    )

    Permission.create(
        name='cloud:volume:view',
        views=[
            read_permission('VolumeList'),
            read_permission('VolumeSingle')
        ]
    )

    Permission.create(
        name='cloud:volume:manage',
        views=[
            create_read_permission('VolumeList'),
            read_update_delete_permission('VolumeSingle')
        ]
    )

    Permission.create(
        name='project:project:view',
        views=[
            read_permission('ProjectList'),
            read_permission('ProjectSingle')
        ]
    )

    Permission.create(
        name='project:project:manage',
        views=[
            create_read_permission('ProjectList'),
            read_update_delete_permission('ProjectSingle'),
            update_delete_permission('ProjectMembership')

        ]
    )

    Permission.create(
        name='fabric:setting:manage',
        views=[
            read_permission('SettingsList'),
            read_update_permission('SettingSingle'),
            create_read_permission('NTPSettingList'),
            read_update_delete_permission('NTPSettingSingle')
        ]
    )

    Permission.create(
        name='fabric:setting:view',
        views=[
            read_permission('SettingsList'),
            read_permission('SettingSingle'),
            read_permission('SettingSingleRetrieve'),
            read_permission('NTPSettingList'),
            read_permission('NTPSettingSingle')
        ]

    )

    Permission.create(
        name='fabric:setting:test',
        views=(
            create_permission('NTPAction'),
            create_permission('SMTPRelayAction')
        )
    )

    Permission.create(
        name='fabric:zone:view',
        views=[
            read_permission('ZoneList'),
            read_permission('ZoneSingle')
        ]
    )

    Permission.create(
        name='fabric:zone:manage',
        views=[
            create_read_permission('ZoneList'),
            read_update_delete_permission('ZoneSingle')
        ]
    )

    Permission.create(
        name='user_management:globalgroup:view',
        views=[
            read_permission('GlobalGroupList'),
            read_permission('GlobalGroupSingle')
        ]
    )

    Permission.create(
        name='user_management:globalgroup:manage',
        views=[
            create_read_permission('GlobalGroupList'),
            read_update_delete_permission('GlobalGroupSingle')
        ]
    )

    Permission.create(
        name='user_management:projectgroup:view',
        views=[
            read_permission('ProjectGroupList'),
            read_permission('ProjectGroupSingle'),
            read_permission('ProjectGroupsPerProject')
        ]
    )

    Permission.create(
        name='user_management:projectgroup:manage',
        views=[
            create_read_permission('ProjectGroupList'),
            read_update_delete_permission('ProjectGroupSingle')
        ]
    )

    Permission.create(
        name='user_management:user:view',
        views=[
            read_permission('UserList'),
            read_permission('UserSingle'),
            read_permission('UsersByProjectSingle'),
            read_permission('UsersByProjectSingle')
        ]
    )

    Permission.create(
        name='user_management:user:manage',
        views=[
            create_read_permission('UserList'),
            read_update_delete_permission('UserSingle'),
            create_read_permission('UsersByProjectList'),
            read_update_delete_permission('UsersByProjectSingle')
        ]
    )

    Permission.create(
        name='cloud:service:view',
        views=[
            read_permission('ServiceList'),
            read_permission('ServiceSingle')
        ]
    )

    Permission.create(
        name='cloud:service:manage',
        views=[
            create_read_permission('ServiceList'),
            read_delete_permission('ServiceSingle')
        ]
    )

    Permission.create(
        name='cloud:stack:view',
        views=[
            read_permission('StackList'),
            read_permission('StackSingle')
        ]
    )

    Permission.create(
        name='cloud:stack:manage',
        views=[
            create_read_permission('StackList'),
            read_delete_permission('StackSingle')
        ]
    )

    Permission.create(
        name='cloud:layer:view',
        views=[
            read_permission('LayerList'),
            read_permission('LayerSingle'),
            read_permission('LayerUpload')
        ]
    )

    Permission.create(
        name='cloud:layer:manage',
        views=[
            create_read_permission('LayerList'),
            read_delete_permission('LayerSingle'),
            read_update_permission('PlaybookSingle')
        ]
    )


def populate_roles(apps, schema_editor):
    """
    Populates the roles with appropriate permissions
    """
    global_administrator = Role.objects.create(name=Role.GLOBAL_ADMINISTRATOR)
    global_spectator = Role.objects.create(name=Role.GLOBAL_SPECTATOR)
    default_spectator = Role.objects.create(name=Role.DEFAULT_SPECTATOR)

    project_user = Role.objects.create(name=Role.PROJECT_USER)
    project_administrator = Role.objects.create(name=Role.PROJECT_ADMINISTRATOR)
    project_spectator = Role.objects.create(name=Role.PROJECT_SPECTATOR)

    global_administrator.permissions.set(Permission.objects.all())

    global_spectator.permissions.set(
        Permission.objects.filter(name__endswith=':view')
        | Permission.objects.filter(name__endswith=':test')
    )

    default_spectator.permissions.add(
        Permission.objects.get(name='kamaji:link:view'),
        Permission.objects.get(name='cloud:service:view'),
        Permission.objects.get(name='cloud:layer:view'),
        Permission.objects.get(name='cloud:stack:view'),
        Permission.objects.get(name='cloud:image:view'),
        Permission.objects.get(name='cloud:flavor:view'),
        Permission.objects.get(name='cloud:overlaynetwork:view')
    )

    project_administrator.permissions.add(
        Permission.objects.get(name='cloud:instance:manage'),
        Permission.objects.get(name='cloud:volume:manage'),
        Permission.objects.get(name='cloud:service:manage'),
        Permission.objects.get(name='project:project:manage'),
        Permission.objects.get(name='user_management:projectgroup:view'),
        Permission.objects.get(name='user_management:user:manage')
    )

    project_user.permissions.add(
        Permission.objects.get(name='cloud:instance:manage'),
        Permission.objects.get(name='cloud:volume:manage'),
        Permission.objects.get(name='cloud:service:manage'),
        Permission.objects.get(name='project:project:view'),
        Permission.objects.get(name='user_management:projectgroup:view'),
        Permission.objects.get(name='user_management:user:view')
    )

    project_spectator.permissions.add(
        Permission.objects.get(name='cloud:instance:view'),
        Permission.objects.get(name='cloud:volume:view'),
        Permission.objects.get(name='cloud:service:view'),
        Permission.objects.get(name='project:project:view'),
        Permission.objects.get(name='user_management:projectgroup:view'),
        Permission.objects.get(name='user_management:user:view')
    )


def add_global_administrator_group(apps, schema_editor):
    """ Create a global group for all supervisor users """
    administrator_role = Role.objects.get(name=Role.GLOBAL_ADMINISTRATOR)
    global_spectator_role = Role.objects.get(name=Role.GLOBAL_SPECTATOR)
    default_spectator_role = Role.objects.get(name=Role.DEFAULT_SPECTATOR)

    GlobalGroup.objects.create(
        name=GlobalGroup.ADMINISTRATORS,
        role=administrator_role
    )

    GlobalGroup.objects.create(
        name=GlobalGroup.SPECTATORS,
        role=global_spectator_role
    )

    GlobalGroup.objects.create(
        name=GlobalGroup.DEFAULT_SPECTATORS,
        role=default_spectator_role
    )


class Migration(migrations.Migration):
    dependencies = [
        ('user_management', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(setup_permissions),
        migrations.RunPython(populate_roles),
        migrations.RunPython(add_global_administrator_group)
    ]
