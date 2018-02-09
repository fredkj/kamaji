# -*- coding: utf-8 -*-
import itertools
import logging

from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.core.mail import EmailMessage
from django.db import models
from django.utils.encoding import python_2_unicode_compatible
from jinja2 import Template
from rest_framework import permissions

from shared import dnshelper
from shared.exceptions import InvalidSSHKeyError
from shared.formatters import remove_hidden_chars
from shared.models import KamajiModel
from shared.openstack2.exceptions import ConflictError, BadRequest
from shared.openstack2.fields import RemoteField, RemoteCharField
from shared.openstack2.models import OSModel
from shared.openstack2.shortcuts import OSResourceShortcut
from shared.rest_validators import validate_ssh_key

logger = logging.getLogger(__name__)


RESET_PASSWORD_EMAIL_TEMPLATE = Template(
    'Hi {{ user.user.first_name }}, \n'
    'We have received a request to reset your password for the '
    'account "{{ user.user.username }}".\n\n'
    'To complete the password reset, go to this link '
    '{{ frontend_reset_password_url }}.\n\n'
    'Kind regards, \n'
    'The Kamaji Team'
)


@python_2_unicode_compatible
class Project(OSModel):
    """
    Represents a project in Kamaji.
    """
    domain_id = RemoteField()
    # The length is constrained so our dns names won't be too long
    name = RemoteCharField(max_length=40)
    enabled = RemoteField()
    description = RemoteField()

    @property
    def members(self):
        """
        :return: All users that are members of a Global or Project Group that
         gives access to this project.
        :rtype: list
        """
        # Filter out all users that are attached to a kamajiuser and member
        # of a GlobalGroup or ProjectGroup that gives access to this project.
        return (User.objects.filter(kamajiuser__isnull=False) & (
            User.objects.filter(projectgroups__project=self) |
            User.objects.filter(globalgroups__name__in=[
                GlobalGroup.ADMINISTRATORS, GlobalGroup.SPECTATORS
            ])
        )).distinct()

    class OpenStackMeta:
        service = 'identity'
        resource = 'projects'
        update_method = OSModel.PATCH

    @property
    def dns_zone(self):
        return dnshelper.Zone(self.name)

    def __str__(self):
        return "{0}: '{1}'".format(self.__class__.__name__, self.name)

    def __repr__(self):
        return "<{0}: '{1}' object at {2}>".format(
            self.__class__.__name__,
            self.name,
            hex(id(self))
        )

    def __add_to_admin_role(self):
        """
        Retrieves the admin user and role and associates them with the
        project.
        """
        admin_user = OSResourceShortcut('identity', 'users').get(name='admin')
        admin_role = OSResourceShortcut('identity', 'roles').get(name='admin')

        OSResourceShortcut(
            self.OpenStackMeta.service,
            self.OpenStackMeta.resource,
            path=(
                self.openstack_id,
                'users',
                remove_hidden_chars(admin_user['id']),
                'roles',
                remove_hidden_chars(admin_role['id'])
            )
        ).update('PUT')

    def __add_allow_all_security_group_rule(self):
        # One can view security groups without authorizing with its specific
        # project, but the default security group is not created until someone
        # authenticates towards the new project, without it no group will be
        # created and we would get nothing.
        group = OSResourceShortcut(
            'network',
            'security-groups',
            project=self.openstack_id
        ).get(tenant_id=self.openstack_id)

        rule_request = {
            "security_group_rule": {
                "direction": "ingress",
                "protocol": None,
                "security_group_id": group['id']
            }
        }

        OSResourceShortcut(
            'network',
            'security-group-rules',
            project=self.openstack_id
        ).post(json=rule_request)

    def __create_default_groups(self):
        ProjectGroup.objects.create(
            project=self,
            role=Role.objects.get(name=Role.PROJECT_ADMINISTRATOR)
        )

        ProjectGroup.objects.create(
            project=self,
            role=Role.objects.get(name=Role.PROJECT_USER)
        )

        ProjectGroup.objects.create(
            project=self,
            role=Role.objects.get(name=Role.PROJECT_SPECTATOR)
        )

    def save(self, **kwargs):
        is_creating = not self.is_created
        if is_creating:
            if self.domain_id is None:
                self.domain_id = OSResourceShortcut(
                    'identity',
                    'domains'
                ).get(name='default')['id']

        old = self.__class__.objects.get(id=self.id) \
            if self.is_created else None

        try:
            super(Project, self).save(**kwargs)
        except ConflictError:
            # OpenStack returns a ConflictError when it should return
            # a BadRequest.
            raise BadRequest(
                'A project with name \'{0}\' already exists.'
                .format(self.name)
            )

        if is_creating:
            self.dns_zone.create()
            self.__add_to_admin_role()
            self.__add_allow_all_security_group_rule()
            self.__create_default_groups()
        elif old and old.dns_zone.name != self.dns_zone.name:
            old.dns_zone.name = self.dns_zone.name

    def delete(self):
        self.dns_zone.try_delete()
        super(Project, self).delete()


    @property
    def users(self):
        """
        Get all users in this project.
        """
        users = []
        for group in self.project_groups.all():
            users.extend(group.users.all())
        return users


@python_2_unicode_compatible
class Role(models.Model):
    """
    Represents a set of permissions.
    """
    GLOBAL_ADMINISTRATOR = 'global_administrator'
    GLOBAL_SPECTATOR = 'global_spectator'
    DEFAULT_SPECTATOR = 'default_spectator'

    PROJECT_USER = 'project_user'
    PROJECT_ADMINISTRATOR = 'project_administrator'
    PROJECT_SPECTATOR = 'project_spectator'

    PROJECT_ROLES = (PROJECT_ADMINISTRATOR, PROJECT_USER, PROJECT_SPECTATOR)

    name = models.CharField(
        max_length=100,
        unique=True,
        help_text='The name of this role.'
    )

    def __str__(self):
        return "{0}: '{1}'".format(self.__class__.__name__, self.name)

    def __repr__(self):
        return "<{0}: '{1}' object at {2}>".format(self.__class__.__name__,
                                                   self.name,
                                                   hex(id(self)))


@python_2_unicode_compatible
class Permission(models.Model):
    """
    A named permission that has a relation with a number of ViewPermissions
    that in turn will define create, read, update, and delete permissions for
    a given view.
    """
    name = models.CharField(
        max_length=100,
        unique=True,
        help_text='The name of this permission'
    )
    roles = models.ManyToManyField(
        Role,
        help_text='The roles that has this permission',
        related_name='permissions'
    )

    @classmethod
    def create(cls, name, views):
        new_permission = cls.objects.create(name=name)

        for view in views:
            ViewPermission.objects.create(permission=new_permission, **view)

        return new_permission

    def __str__(self):
        return "{0}: '{1}'".format(self.__class__.__name__, self.name)

    def __repr__(self):
        return "<{0}: '{1}' object at {2}>".format(self.__class__.__name__,
                                                   self.name,
                                                   hex(id(self)))


@python_2_unicode_compatible
class Group(models.Model):
    """
    Represents a group of users that are tied to a Role.
    """
    role = models.ForeignKey(
        Role,
        related_name='%(class)ss',
        help_text='The role that this group maps to'
    )
    users = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        blank=True,
        related_name='%(class)ss',
        help_text='Users to be coupled with this group'
    )

    class Meta:
        abstract = True

    def __str__(self):
        return "{0}: '{1}'".format(self.__class__.__name__, self.name)

    def __repr__(self):
        return "<{0}: '{1}' object at {2}>".format(self.__class__.__name__,
                                                   self.name,
                                                   hex(id(self)))

    def permits_view(self, view_name, method):
        relevant_view_permissions = ViewPermission.objects.filter(
            view_name=view_name,
            permission__in=self.role.permissions.all()
        )

        for view_permission in relevant_view_permissions:
            if view_permission.allows_method(method):
                return True

    def delete(self, **kwargs):
        """
        Delete the Group
        """

        # Before we remove the group, remove all members to make sure that the
        # m2m_changed signal is sent.
        self.users.clear()

        super(Group, self).delete(**kwargs)


@python_2_unicode_compatible
class ProjectGroup(Group):
    """
    Represents a group that is tied to a Kamaji Project.
    """
    project = models.ForeignKey(
        Project,
        related_name='project_groups',
        help_text='The project this group is assigned to.',
    )

    class Meta:
        unique_together = ('project', 'role')

    @property
    def name(self):
        return "{0}-{1}s".format(self.project.name, self.role.name)

    def __str__(self):
        return "{0}: '{1}' for {2}".format(self.__class__.__name__,
                                           self.name,
                                           self.project)

    def __repr__(self):
        return "<{0}: '{1}' object at {2}>".format(self.__class__.__name__,
                                                   self.name,
                                                   hex(id(self)))

    @staticmethod
    def get_instances(project_groups):
        """
        Get all Instances of the projects of the specified ProjectGroups.
        """
        return list(
            itertools.chain(
                *[group.project.active_instance_ips for group in project_groups]
                )
        )


@python_2_unicode_compatible
class GlobalGroup(Group):
    """
    Represents a group that has global access, that is, not tied to a specific
    Kamaji Project.
    """
    ADMINISTRATORS = 'Global Administrators'
    SPECTATORS = 'Global Spectators'
    DEFAULT_SPECTATORS = 'Default Spectators'

    name = models.CharField(
        max_length=100,
        unique=True,
        help_text='Name of this group'
    )

    def __str__(self):
        return "{0}: '{0}'".format(self.__class__.__name__, self.name)

    def __repr__(self):
        return "<{0}: '{1}' object at {2}>".format(self.__class__.__name__,
                                                   self.name,
                                                   hex(id(self)))


@python_2_unicode_compatible
class ViewPermission(models.Model):
    permission = models.ForeignKey(
        Permission,
        related_name='view_permissions',
        help_text='The permission that this ViewPermission belongs to.'
    )
    view_name = models.CharField(max_length=100)
    create = models.BooleanField(
        default=False, help_text='True if create operations are allowed.')
    read = models.BooleanField(
        default=False, help_text='True if read operations are allowed.')
    update = models.BooleanField(
        default=False, help_text='True if update operations are allowed.')
    delete = models.BooleanField(
        default=False, help_text='True if delete operations are allowed.')

    def allows_method(self, method):
        if method in permissions.SAFE_METHODS:
            return self.read
        elif method == 'PUT' or method == 'PATCH':
            return self.update
        elif method == 'POST':
            return self.create
        elif method == 'DELETE':
            return self.delete
        return False

    def __str__(self):
        return "{0}: '{1}'".format(self.__class__.__name__, self.view_name)

    def __repr__(self):
        return "<{0}: '{1}' object at {2}>".format(self.__class__.__name__,
                                                   self.view_name,
                                                   hex(id(self)))


class KamajiUser(KamajiModel):
    user = models.OneToOneField(User)
    ssh_key = models.CharField(max_length=2000, blank=True, null=True)

    def set_project_role(self, project, role_name):
        """
        Sets the project role for this user.
        Assures a user can only have one role within a project by removing any
        roles in the same project before adding the new role.
        :raises: GlobalGroup.DoesNotExist
        """
        try:
            old_group = self.user.projectgroups.get(project=project)
        except ProjectGroup.DoesNotExist:
            old_group = None

        try:
            new_group = ProjectGroup.objects.get(
                project=project,
                role__name=role_name
            )
        except ProjectGroup.DoesNotExist:
            if role_name is not None:
                raise
            new_group = None

        if old_group is not None:
            old_group.users.remove(self.user)

        if new_group is not None:
            new_group.users.add(self.user)

    @property
    def project_roles(self):
        return {group.project: group.role for group
                in self.user.projectgroups.all()}

    @property
    def global_role(self):
        for role_name in [GlobalGroup.ADMINISTRATORS, GlobalGroup.SPECTATORS]:
            try:
                return self.user.globalgroups.get(name=role_name).role
            except GlobalGroup.DoesNotExist:
                pass
        return None

    def set_global_role(self, role_name):
        """
        Sets the global role of the user.
        Assures the user can only have one global role by removing any other
        global role (except the default_spectator role) after adding the new
        one.
        :raises: GlobalGroup.DoesNotExist
        """
        try:
            old_group = self.user.globalgroups.get(role=self.global_role)
        except GlobalGroup.DoesNotExist:
            old_group = None

        try:
            new_group = GlobalGroup.objects.get(role__name=role_name)
        except GlobalGroup.DoesNotExist:
            if role_name is not None:
                raise
            new_group = None

        if old_group is not None:
            old_group.users.remove(self.user)

        if new_group is not None:
            new_group.users.add(self.user)

    def save(self, **kwargs):
        if self.user is None:
            raise AttributeError('A user must be specified.')

        if self.ssh_key:
            try:
                validate_ssh_key(self.ssh_key)
            except InvalidSSHKeyError:
                if self.id is None:
                    # If we are trying to create a user with a non-valid key,
                    # delete the django associated user
                    self.user.delete()
                raise

        super(KamajiUser, self).save(**kwargs)

    def send_password_reset_email(self, hostname):
        token_generator = PasswordResetTokenGenerator()
        token = token_generator.make_token(self.user)

        frontend_reset_password_url=Template(
            settings.FRONTEND_PASSWORD_RESET_PATH
        ).render(
            user=self.user,
            token=token,
            hostname=hostname
        )

        email = EmailMessage(
            'Password reset request',
            RESET_PASSWORD_EMAIL_TEMPLATE.render(
                user=self,
                frontend_reset_password_url=frontend_reset_password_url
            ),
            'noreply@kamaji.io',
            (self.user.email, )
        )

        email.send()

    @staticmethod
    def is_key_valid_or_none(key):
        if key is None:
            return True

        try:
            validate_ssh_key(key)
            return True
        except InvalidSSHKeyError:
            return False
