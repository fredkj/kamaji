# -*- coding: utf-8 -*-
import logging

from ansible.parsing.dataloader import DataLoader
from ansible.vars import VariableManager
from ansible.inventory import Inventory
from ansible.executor.playbook_executor import PlaybookExecutor
from ansible.executor.task_queue_manager import TaskQueueManager
from ansible.playbook.play import Play

from django.conf import settings

from api import celery_app
from fabric.models import Host
from shared.exceptions import AnsibleHostsUnavailableError, KamajiApiException, \
    AnsiblePlaybookError

logger = logging.getLogger(__name__)


class _AnsibleOptions(object):
    """
    Options class to replace Ansible OptParser
    """
    def __init__(self, **kwargs):
        for attribute, value in kwargs.items():
            setattr(self, attribute, value)

    def __getattr__(self, attribute):
        return None


class _AnsibleTask(celery_app.Task):
    """
    "Abstract" super class for Celery tasks that uses Ansible.
    This class is only supposed to define the interface for it's child classes
    and should never be instantiated directly.
    """
    def __init__(self):
        self.variable_manager = VariableManager()
        self.loader = DataLoader()
        self.options = _AnsibleOptions(
            remote_user='kamaji',
            connection='ssh',
            private_key_file=settings.ANSIBLE['keys']['private'],
            become_user='root',
            become_method='sudo',
            become=True,
            forks=20
        )

    def execute(self, item_to_execute, args, hosts):
        raise NotImplemented

    @staticmethod
    def validate(response):
        """
        Checks the response of an ansible runner call for failed
        executions and unreachable hosts.

        :param response: The response from running Ansible Runner
        :type response: dict
        """
        if len(response.dark) > 0:
            raise AnsibleHostsUnavailableError
        elif len(response.failures) > 0:
            raise AnsiblePlaybookError


class AnsibleRunnerTask(_AnsibleTask):
    """
    This class facilitates running a Celery task using an Ansible module.
    """
    def execute(self, module, host, become=None):
        """
        Run an Ansible module on a specific host.

        :param module: The module to execute.
        :type module: str
        :param host: The ip of the host to run the module on.
        :type host: str
        :param become: Use privilege escalation to become another user than the currently logged in one.
        :return: The corresponding hostvars.
        :rtype: :class:`HostVars`
        """
        if become is not None:
            self.options.become = become

        inventory = Inventory(
            loader=self.loader,
            variable_manager=self.variable_manager,
            host_list=[host]
        )

        play_module = {
            "name": "Run module {}".format(module),
            "hosts": host,
            "gather_facts": "no",
            "tasks": [
                {"action": {"module": module}}
            ]
        }

        play = Play().load(
            play_module,
            variable_manager=self.variable_manager,
            loader=self.loader
        )

        tqm = None
        try:
            tqm = TaskQueueManager(
                inventory=inventory,
                variable_manager=self.variable_manager,
                loader=self.loader,
                options=self.options,
                passwords={}
            )
            tqm.run(play)

            self.validate(tqm._stats)
            logger.info('Module {0} successful'.format(module))

            return tqm.hostvars
        finally:
            if tqm is not None:
                tqm.cleanup()


class AnsiblePlaybookTask(_AnsibleTask):
    """
    This class facilitates running a Celery task using an Ansible playbook.
    """
    def execute(self,
                playbook_name,
                args,
                hosts,
                private_key_file=None,
                remote_user=None):
        """
        Run an Ansible playbook on a specific set of hosts.

        :param playbook_name: The name of the playbook.
        :type playbook_name: str
        :param args: Arguments to the playbook.
        :type args: dict
        :param hosts: A list of hosts to execute the playbook on.
        :type hosts: list
        :param private_key_file: A path to the private key for the connection.
        :type private_key_file: str
        :param remote_user: The user to execute the playbook as.
        :type remote_user: str
        :return: The resulting TaskQueueManager.
        :rtype: :class:`TaskQueueManager`
        """
        if private_key_file is not None:
            self.options.private_key_file = private_key_file
        if remote_user is not None:
            self.options.remote_user = remote_user

        inventory = Inventory(
            loader=self.loader,
            variable_manager=self.variable_manager,
            host_list=hosts
        )

        self.variable_manager.extra_vars = args

        play = PlaybookExecutor(
            playbooks=[playbook_name],
            inventory=inventory,
            variable_manager=self.variable_manager,
            loader=self.loader,
            options=self.options,
            passwords={}
        )

        play.run()

        self.validate(play._tqm._stats)
        logger.info('Playbook {0} successful'.format(playbook_name))

        return play._tqm
