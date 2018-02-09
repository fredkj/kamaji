# -*- coding: utf-8 -*-
import json
import logging

from datetime import datetime
from time import ctime

import ntplib
from django.db import models

from fabric.tasks import ConfigureNTPServersTask

logger = logging.getLogger(__name__)


class Setting(models.Model):
    """
    A global setting i Kamaji.
    """
    setting = models.CharField(max_length=255)
    data = models.TextField()

    @property
    def value(self):
        return json.loads(self.data)

    @value.setter
    def value(self, new_value):
        if not isinstance(new_value, dict):
            raise ValueError('Value must be a dict')

        self.data = json.dumps(new_value)

    def __getattr__(self, item):
        try:
            return self.value[item]
        except KeyError:
            raise AttributeError

    class Meta:
        app_label = 'fabric'

    def __str__(self):
        return 'Name: {0}, Data: {1}'.format(self.setting, self.data)

    def __repr__(self):
        return "<{0}: '{1}' object at {2}>".format(self.__class__.__name__,
                                                   self.setting,
                                                   hex(id(self)))


class NTPSetting(models.Model):
    """
    Configures NTP servers in Kamaji.
    """
    CONNECTION_UP = 'up'
    CONNECTION_ERROR = 'error'
    CONNECTION_NOT_CONNECTED = 'not connected'
    CONNECTION_STATUSES = (
        (CONNECTION_UP, CONNECTION_UP),
        (CONNECTION_ERROR, CONNECTION_ERROR),
        (CONNECTION_NOT_CONNECTED, CONNECTION_NOT_CONNECTED)
    )

    QUEUED = 'queued'
    ACTIVE = 'active'
    INTERNAL_ERROR = 'internal error'
    STATUSES = (
        (QUEUED, QUEUED),
        (ACTIVE, ACTIVE),
        (INTERNAL_ERROR, INTERNAL_ERROR)
    )

    address = models.CharField(max_length=255)

    status = models.CharField(
        default=QUEUED,
        choices=STATUSES,
        max_length=64
    )

    connection_status = models.CharField(
        default=CONNECTION_NOT_CONNECTED,
        choices=CONNECTION_STATUSES,
        max_length=64
    )

    last_test = models.DateTimeField(null=True)
    last_test_stratum = models.IntegerField(null=True)

    class Meta:
        app_label = 'fabric'

    @classmethod
    def set_all_statuses(cls, status):
        for setting in cls.objects.all():
            setting.status = status
            setting.save(do_ntp_server_update=False)

    def test(self):
        ntp_client = ntplib.NTPClient()
        self.last_test = datetime.utcnow()

        try:
            ntp_response = ntp_client.request(str(self.address))
            self.last_test_stratum = ntp_response.stratum
            self.connection_status = NTPSetting.CONNECTION_UP

            logging.info(
                'Successfully tested NTP server with status %s '
                'and stratum %s.',
                self.connection_status,
                self.last_test_stratum
            )

            response = {
                'time': ctime(ntp_response.tx_time),
                'stratum': ntp_response.stratum,
                'connection_status': self.connection_status
            }

        except Exception as e:
            logging.exception('Error while testing NTP server.')
            self.last_test_stratum = None
            self.connection_status = NTPSetting.CONNECTION_ERROR
            message = 'Connection Error' if e.message == '' else e.message

            response = {
                'connection_status': self.connection_status,
                'message': 'Error: {0}'.format(message)
            }

        finally:
            self.save(do_ntp_server_update=False)

        return response

    def save(self, do_ntp_server_update=True, *args, **kwargs):
        super(NTPSetting, self).save(*args, **kwargs)

        if do_ntp_server_update:
            ConfigureNTPServersTask().delay(self)
