# -*- coding: utf-8 -*-
from time import sleep

from proxmoxer import ProxmoxAPI


class VirtualMachineCollection(object):
    """
    Provides functionality to restart all virtual compute nodes
    for an environment that is running in a proxmox cluster.
    """
    CLUSTER_INFO = {
        'host': '172.20.5.12',
        'user': 'integration@pve',
        'password': 'kamaji',
        'verify_ssl': False
    }

    def __init__(self, environment):
        """
        :param environment: Which environment to get VMs from.
        :type environment: str
        """
        self.environment = environment
        self._api = None

    @property
    def api(self):
        """
        Creates a connection to the proxmox API.
        :return: A proxmox API object
        :rtype: obj
        """
        if self._api is None:
            self._api = ProxmoxAPI(**self.CLUSTER_INFO)
        return self._api

    @property
    def _vms(self):
        """
        Returns a list of all VMs for the environment.
        :return: List of all VMs for the environment
        :rtype: list
        """
        return [
            vm
            for vm in self.api.cluster.resources.get(type='vm')
            if vm['name'].split('.')[1] == self.environment
        ]

    def _is_running(self, node, vmid):
        """
        Check if a VM is running or not
        :param node: A proxmox node object
        :type node: obj
        :param vmid: Id of the VM
        :type vmid: int
        :return: True if running, False if not
        :rtype: bool
        """
        return node.qemu(vmid).status.current.get()['status'] == 'running'

    def _set_state(self, node, vmid, started):
        """
        Set all VMs to the desired state.
        :param node: A proxmox node object
        :type node: obj
        :param vmid: Id of the VM
        :type vmid: int
        :param started: If the VM should be running or not
        :type started: bool
        """
        if started:
            node.qemu(vmid).status.start.post()
        else:
            node.qemu(vmid).status.stop.post()

        count = 0
        while self._is_running(node, vmid) != started:
            count += 1
            if count == 15:
                raise Exception("Timeout")
            sleep(1)

    def start(self):
        """
        Starts all VMs for the environment.
        """
        for vm in self._vms:
            node = self.api.nodes(vm['node'])
            vmid = vm['vmid']

            if not self._is_running(node, vmid):
                self._set_state(node, vmid, started=True)

    def stop(self):
        """
        Stop all VMs for the environment.
        """
        for vm in self._vms:
            node = self.api.nodes(vm['node'])
            vmid = vm['vmid']

            if self._is_running(node, vmid):
                self._set_state(node, vmid, started=False)

    def restart(self):
        """
        Stops and starts all VMs for the environment.
        """
        self.stop()
        self.start()
