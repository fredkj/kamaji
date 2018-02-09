# -*- coding: utf-8 -*-
from django.db import models

import fabric.models
from shared.models import KamajiModel


class Host(KamajiModel):
    """
    Stores a Controller host indexed by type and optionally an index.
    Hosts are tied to the controller specified by the index field if it is
    specified and it exists.
    Some hosts such as the loadbalancer stored with type:'vip' has only one
    possible value and so needs no index.

    Example::

        vip_host = Host.objects.get(type='vip')
        secondary_controller_nameserver_host = Host.objects.get(type='ns', index=1)

    """

    ip_address = models.GenericIPAddressField(protocol='IPv4', unique=True)
    type = models.CharField(max_length=50)
    index = models.IntegerField(default=None, null=True, blank=True)

    class Meta:
        app_label = 'fabric'
        unique_together = ('type', 'index')
        ordering = ['index']

    def __str__(self):
        return 'Hostname: {0}, IP Address: {1}'.format(
            self.hostname, self.ip_address
        )

    def __repr__(self):
        return "<{0}: '{1}' object at {2}>".format(
            self.__class__.__name__, self.hostname, hex(id(self))
        )

    @property
    def hostname(self):
        return '{0}{1}'.format(self.type, self.index or '')

    def save(self, *args, **kwargs):
        is_creating = not self.is_created

        super(Host, self).save(*args, **kwargs)

        # If we are creating a new Host, try to tie it to the appropriate
        # controller, if such exists
        if is_creating:
            Controller = fabric.models.Controller
            controller_primary = self.index == 1

            try:
                controller = Controller.objects.get(
                    primary=controller_primary
                )
                controller.host_map.create(host=self)
            except Controller.DoesNotExist:
                pass
