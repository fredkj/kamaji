# -*- coding: utf-8 -*-
import pdnsapi
from django.conf import settings
from pdnsapi.exceptions import (
    PDNSNotFoundException, PDNSProtocolViolationException
)

from shared.exceptions import KamajiApiException


class Zone(object):
    RECORD_TYPE = 'A'

    def __init__(self, name):
        if not name:
            raise ValueError('Name cannot be None.')

        self._name = name
        self.__zone = None
        super(Zone, self).__init__()

    @property
    def name(self):
        return self._name

    @name.setter
    def name(self, new_name):
        if self._name != new_name:
            canonical_name = self._get_canonical_zone_name(new_name)
            self._connection.rename_zone(self._zone, canonical_name)
            self._name = new_name
            # Reset zone so the new one will be fetched
            self.__zone = None

    @property
    def _zone(self):
        if self.__zone is None:
            self.__zone = self._connection.get_zone(
                self._get_canonical_zone_name(self.name)
            )
        return self.__zone

    @classmethod
    def _get_connection(cls):
        from fabric.models import Credential, Host

        if Host.objects.filter(type='vip').exists():
            creds = Credential.get_credential(Credential.POWERDNS_API_KEY)
            host_url = Host.objects.get(type='vip').ip_address
            url = '{0}://{1}:{2}'.format(
                settings.POWERDNS_SCHEMA, host_url, settings.POWERDNS_PORT)
            return pdnsapi.init_api(url, 'localhost', creds.password)
        else:
            raise KamajiApiException('VIP address is not configured so cannot '
                                     'configure DNS names.')

    @classmethod
    def _get_nameservers(cls):
        return [
            cls._get_canonical_zone_name('ns01'),
            cls._get_canonical_zone_name('ns02')
        ]

    @staticmethod
    def _get_canonical_zone_name(name):
        from fabric.models import Setting
        domain = Setting.objects.get(setting='DomainSetting').domain

        return Zone._to_canonical('{0}.kamaji.{1}.'.format(name, domain))

    @property
    def _connection(self):
        return self._get_connection()

    @staticmethod
    def _to_canonical(name):
        return name.replace(' ', '-').lower()

    def get_fqdn(self, hostname):
        return self._to_canonical('{0}.{1}'.format(hostname, self._zone.name))

    def add_record(self, hostname, *addresses):
        if len(addresses) < 1:
            ValueError('At least one address must be provided.')

        fqdn = self.get_fqdn(hostname)
        record = pdnsapi.Record(fqdn, self.RECORD_TYPE, addresses)
        self._zone.add_record(record)
        # Reset the zone so the new record representation will be fetched
        self.__zone = None

    def remove_record(self, hostname):
        fqdn = self.get_fqdn(hostname)
        record = pdnsapi.Record(fqdn, self.RECORD_TYPE, [])
        self._zone.delete_record(record)
        # Reset the zone so the new record representation will be fetched
        self.__zone = None

    def try_remove_record(self, hostname):
        """
        Tries to remove the record with the specified hostname.
        :return: True if the record was removed, False if the record already
        was non-existent.
        :rtype: bool
        """
        if not self.exists():
            return False

        try:
            self.remove_record(hostname)
            return True
        except ValueError:
            # There's no record with this hostname
            return False
        except PDNSProtocolViolationException:
            # There's no zone with this name
            return False

    def rename_record(self, old_hostname, new_hostname):
        if old_hostname != new_hostname:
            record = self._zone.get_record(
                self.get_fqdn(old_hostname),
                self.RECORD_TYPE
            )
            self.add_record(new_hostname, record.records[0])
            self.try_remove_record(old_hostname)
            return True

        return False

    def has_record(self, hostname):
        try:
            self._zone.get_record(self.get_fqdn(hostname), self.RECORD_TYPE)
            return True
        except PDNSNotFoundException:
            return False

    def exists(self):
        try:
            return self._zone is not None
        except PDNSProtocolViolationException:
            return False

    def delete(self):
        self._connection.delete_zone(self._zone.name)

    def try_delete(self):
        """
        Tries to delete the zone.
        :return: True if the zone was deleted, False if the zone already was
        non-existent.
        :rtype: bool
        """
        try:
            self.delete()
            return True
        except PDNSProtocolViolationException:
            # The zone didn't exist
            return False

    def create(self):
        """
        Create the zone if it does not exist.
        :return: True if the zone was created, False otherwise.
        :rtype: bool
        """
        try:
            self._get_connection().create_zone(
                self._get_canonical_zone_name(self.name),
                self._get_nameservers()
            )
            return True
        except PDNSProtocolViolationException:
            # The zone already exists
            return False
