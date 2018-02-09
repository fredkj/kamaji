# -*- coding: utf-8 -*-
import logging

from django.conf import settings

from shared.ansible_tasks import AnsiblePlaybookTask

logger = logging.getLogger(__name__)


class ManageUserKeyTask(AnsiblePlaybookTask):
    """
    Task to manage ssh keys of users on instances.

    This class is not to be instantiated directly, it serves as a superclass
    for specific subclasses that deploys keys in different ways.
    """
    ignore_result = False

    def _manage_user(self, user, instances, present=True):
        """
        Method that adds/removes a user together with an SSH key to a one or
        many instances.

        :param user: The user for which to add/remove an account on the
            instance
        :type user: user_management.models.User
        :param instances: The instances where to add/remove the account
        :type instances: list
        :param present: Whether the user should be be present (be added) or not
            (be removed) on the instance.
        :type present: bool
        :return: The added/removed user
        :rtype: User
        """
        if instances:
            extra_vars = {
                'user': {
                    'name': user.username,
                    'state': 'present' if present else 'absent',
                    'sudo': True
                }
            }

            if hasattr(user, 'kamajiuser') and present:
                extra_vars['user']['key'] = user.kamajiuser.ssh_key
            else:
                extra_vars['user']['key'] = None

            self.execute(
                'user_management/ansible/manage_user_key.yml',
                extra_vars,
                instances,
                settings.PROVISIONING_KEY,
                'ubuntu'
            )

        return user

    @classmethod
    def get_chain(cls, users, *args, **kwargs):
        """
        Abstract method for returning a chain of Ansible tasks. Needs to be
        overridden by the extending class.

        :param users: The list of users that the chain should be created for
        :type users: list
        :raises: NotImplementedError
        """
        raise NotImplementedError


class ManageUserKeyStandaloneTask(ManageUserKeyTask):
    """
    Task to manage ssh keys of users on instances.
    To be used when all parameters are known at creation of the task.
    """
    def run(self, user, instances, present=True):
        """
        Add/remove a user account for a specified User to a series of
        instances.

        :param user: The user for which to add/remove an account
        :type user: user_management.models.User
        :param instances: A list of instances where user account should be
            added/removed
        :type instances: list
        :param present: Whether the user account should be added or removed
        :type present: bool
        :return: The user
        :rtype: user_management.models.User
        """
        return self._manage_user(user, instances, present)

    @classmethod
    def get_chain(cls, users, instances, present=True):
        """
        Returns a chain of ManageUserKeyStandaloneTask chained together without
        interactive parameters.

        :param users: List of users to create tasks for.
        :type users: list
        :param instances: Instances to add/remove the users to.
        :type instances: list
        :param present: Should the user ssh keys be added or removed.
        :type present: bool
        :return: Generator containing immutable ManageUserKeyStandaloneTask
            i.e. chained together without support for interactive parameters.
        :rtype: generator
        """
        return (cls().si(
            user, instances, present
        ) for user in set(users))


class ManageUserKeyChainedTask(ManageUserKeyTask):
    """
    Task to manage ssh keys of users on instances.

    Returns the same output as LayerTasks and expects the same interactive
    parameters and can therefore easily be chained together with such tasks.
    To be used when the instance addresses are not known at creation of
    the task.
    """
    def run(self, (instance_addresses, service), user):
        """
        Add/remove a user account for a specified User to a series of
        instances.

        :param user: The user to add/remove to the instance
        :type user: user_management.models.User
        :return: The instance address and the service.
        :rtype: tuple
        """
        self._manage_user(user, instance_addresses)

        return instance_addresses, service

    @classmethod
    def get_chain(cls, users):
        """
        Creates a chain of ManageUserKeyChainedTask.

        :param users: The users to create tasks for.
        :type users: list
        :return: Generator containing ManageUserKeyChainedTask chained together
        with support for interactive parameters.
        :rtype: generator
        """
        return (cls().s(user=user) for user in set(users))
