# -*- coding: utf-8 -*-
import logging
import os
import sys

import errno
import yaml

from django.core.management.base import BaseCommand
from django.conf import settings

from fabric.models import (
    Credential, SSHKey, Host, Setting, NTPSetting, ImagePlaceholder, Image,
    PhysicalNetwork
)
from fabric.models import Flavor
from shared.exceptions import KamajiOpenStackError
from shared.openstack2 import OSResourceShortcut, NotFoundError

logger = logging.getLogger(__name__)


class CredentialParser(object):
    """
    Parser to parse a YAML config file generated during install time into
    create statements for Kamaji models.
    """
    def __init__(self, config):
        """
        :param config: The configuration represented as a dict.
        :type config: Dict
        """
        self.config = config

    def parse_passwords(self):
        """
        Parse all passwords and tokens into Credential models.
        """
        logger.info('Parsing Passwords and Tokens...')
        self.__parse_users('mariadb_settings', 'mariadb')

        self.__parse_users('openstack_settings', 'openstack')
        self.__parse_single_credential('openstack_settings', 'openstack',
                                       'metadata_secret')
        self.__parse_single_credential('openstack_settings', 'openstack',
                                       'admin_token')

        self.__parse_single_credential('powerdns_settings', 'powerdns',
                                       'api_key')

        self.__parse_users('rabbitmq_settings', 'rabbitmq')
        logger.info('Finished parsing Passwords and Tokens.')

    def parse_keys(self):
        """
        Parse all SSH keys into SSHKey models.
        """
        logger.info('Parsing Keys...')
        self.__parse_single_ssh_key('service_settings', 'kamaji', 'ssh_key')
        logger.info('Finished parsing Keys.')

    def __parse_single_credential(self, collection, service, item):
        Credential.objects.create(
            service=self.__get_service_tag(service, item), username=item,
            password=self.config[collection][item])

    def __parse_users(self, collection, service):
        for username, item in self.config[collection]['users'].items():
            Credential.objects.create(
                service=self.__get_service_tag(service, username),
                username=username, password=item['password'])

    def __parse_single_ssh_key(self, collection, service, item):
        SSHKey.objects.create(service=self.__get_service_tag(service, item),
                              key=self.config[collection][item])

    @staticmethod
    def __get_service_tag(service, username):
        return '{0}_{1}'.format(service, username)

    @staticmethod
    def clean_credentials_and_ssh_keys():
        Credential.objects.all().delete()
        SSHKey.objects.all().delete()
        Host.objects.all().delete()


class SettingsParser(object):
    """
    Parser to parse a YAML config file generated during install time into
    create statements for Kamaji models.
    """
    def __init__(self, config):
        """
        :param config: The configuration represented as a dict
        :type config: Dict
        """
        self.config = config

    def parse_resolvers(self):
        """
        Parse DNS resolvers
        """
        logger.info('Parsing DNS resolvers...')
        Setting.objects.create(
            setting='ResolverSetting',
            value={'resolvers': self.config['service_settings']['dns']}
        )
        logger.info('Finished parsing DNS resolvers.')

    def parse_ntp(self):
        """
        Parse NTP servers
        """
        logger.info('Parsing NTP servers... ')
        for server in self.config['service_settings']['ntp']:
            NTPSetting.objects.create(address=server)
        logger.info('Finished parsing NTP servers.')

    def parse_domain(self):
        """
        Parse domain name
        """
        logger.info('Parsing domain name...')
        Setting.objects.create(
            setting='DomainSetting',
            value={
                'domain': self.config['service_settings']['domain']
            })
        logger.info('Finished parsing domain name.')

    def add_smtp_setting(self):
        logger.info('Adding SMTP settings')
        Setting.objects.create(
            setting='SMTPRelaySetting',
            value={
                'connection_security': 'tls',
                'smtp_port': 587,
                'smtp_host': 'smtp-relay.gmail.com'
            }
        )
        logger.info('Finished adding SMTP settings')


def parse_hosts(config):
    """
    Parse all hosts in the configuration.
    :param config: The configuration represented as a dict.
    """
    logger.info('Parsing Hosts...')
    for host, data in config['service_nodes'].items():
        Host.objects.create(
            type='controller',
            index=host,
            ip_address=data.get('ipv4_address', None)
        )

        for container_name, container in data['containers'].items():
            Host.objects.create(
                type=container_name,
                index=host,
                ip_address=container.get('ipv4_address', None)
            )

    # Create a new Host instance for the VIP address outside of the loop,
    # since there is only one, unlike the other hosts that are available in
    # pairs.
    Host.objects.create(
        type='vip',
        ip_address=config['service_applications']['vip_ipv4_address']
    )

    logger.info('Finished parsing Hosts.')


def parse_controller_network(config):
    """
    Parse the controller network in the configuration
    :param config: The configuration represented as a dict.
    """
    logger.info('Parsing controller network...')
    PhysicalNetwork.controller_networks.all().delete()

    network = config['service_networks']['flat']

    # Get the first and last valid host address in the range
    range_start, range_end = PhysicalNetwork.get_range(
        network['ipv4_subnet'],
        network['ipv4_prefix'],
        network['ipv4_gateway']
    )

    PhysicalNetwork.objects.create(
        name='controller_network',
        subnet=network['ipv4_subnet'],
        prefix=network['ipv4_prefix'],
        gateway=network['ipv4_gateway'],
        range_start=range_start,
        range_end=range_end,
        type="controller_network"
    )

    logger.info('Finished parsing controller network.')


def populate_image_placeholders():
    logger.info('Populating image placeholders.')
    ImagePlaceholder.objects.all().delete()

    ImagePlaceholder.objects.create(
        name=Image.UBUNTU_16_04, protected=True, visibility='public',
        container_format=ImagePlaceholder.BARE,
        disk_format=ImagePlaceholder.QCOW2,
        url='http://cloud-images.ubuntu.com/xenial/current/'
            'xenial-server-cloudimg-amd64-disk1.img',
        kamaji_services_compatible=True
    )

    logger.info('Finished populating image placeholders.')


def populate_openstack_keypair():
    """
    Create the keypair in OpenStack that will be used for all instance
    integrations.

    Depends on openstack credentials so must be run after all hosts has been
    populated.
    """
    logger.info('Populating OpenStack keypair.')
    try:
        OSResourceShortcut(
            'compute',
            'os-keypairs',
            path=settings.OPENSTACK_INSTANCE_KEY_NAME
        ).get()
        logger.info('There is an existing OpenStack keypair. Will leave it.')
        logger.info('Finished populating OpenStack keypair.')
    except NotFoundError:
        logger.info('There is no existing OpenStack keypair. Will create one.')
        try:
            logger.info('Creating new OpenStack keypair.')
            keypair = OSResourceShortcut('compute', 'os-keypairs').post(
                json={'keypair': {
                    'name': settings.OPENSTACK_INSTANCE_KEY_NAME
                }}
            )
            store_provisioning_key(keypair['private_key'])
            logger.info('Finished populating OpenStack keypair.')
        except KamajiOpenStackError:
            logger.exception('Could not create OpenStack keypair.')
            raise
        except:
            # If something fails here we will want to be able to search the
            # logs for one specific log message, hence the broad except.
            logger.exception(
                'Could not contact OpenStack when trying to create'
                'instance keypair.')
            raise
    except:
        # If something fails here we will want to be able to search the logs
        # for one specific log message, hence the broad except.
        logger.exception('Could not contact OpenStack when trying to get '
                         'existing instance keypair.')
        raise


def store_provisioning_key(private_key):
    logger.info('Checking if provisioning key folder exists.')
    if not os.path.exists(os.path.dirname(settings.PROVISIONING_KEY)):
        try:
            logger.info('Creating provisioning key directory')
            os.makedirs(os.path.dirname(settings.PROVISIONING_KEY))
        except OSError as exc:
            if exc.errno != errno.EEXIST:
                logger.exception('Can not create provisioning key directory.')
                raise

    logger.info('Creating provisioning key.')
    with open(settings.PROVISIONING_KEY, 'w') as f:
        os.chmod(settings.PROVISIONING_KEY, 0o600)
        f.write(private_key)
        logger.info('Done creating provisioning key.')


def populate_zone_limit_setting():
    logger.info('Populating ZoneLimitSetting.')
    Setting.objects.create(
        setting='ZoneLimitSetting',
        value={'zone_limit': settings.DEFAULT_ZONE_LIMIT}
    )
    logger.info('Finished populating ZoneLimitSetting.')


def synchronize():
    """
    Synchronizes our database with OpenStack and populates all Models that
    comes with preset resources.
    """
    Flavor.synchronize()


class Command(BaseCommand):
    """
    Parse the specified YAML configuration file into Kamaji models.
    Flags: --file: Specify where the config file resides, defaults to 'all'.
    """
    help = 'Load configurations from a YAML file into Kamaji models.'

    def handle(self, *args, **options):
        """
        Parse configuration data, exit if the specified file does not exist.
        :param args: Not used.
        :param options: Optional args, may contain 'file'.
        """
        logger.info('Parsing configuration...')

        # Remove all current configuration so we can retry parsing on failure.
        logger.info('Removing old configuration, if any...')

        CredentialParser.clean_credentials_and_ssh_keys()
        Setting.objects.all().delete()

        logger.info('Finished removing old configuration.')

        try:
            filename = options['file']
            with open(filename, 'r') as f:
                logger.info("Reading configuration file at '{0}'."
                            .format(filename))
                config = yaml.load(f)
                logger.info("Successfully read configuration file at '{0}'."
                            .format(filename))
        except IOError as e:
            # TODO: Can ansible pick up status codes?
            # If not does it pick up exceptions?
            # In that case we should change this to an exception so the
            # installer knows it went caca.
            logger.exception(e)
            sys.exit(1)

        populate_image_placeholders()

        parse_hosts(config)

        cred_parser = CredentialParser(config)
        cred_parser.parse_passwords()
        cred_parser.parse_keys()

        setting_parser = SettingsParser(config)
        setting_parser.parse_resolvers()
        setting_parser.parse_domain()
        setting_parser.parse_ntp()
        setting_parser.add_smtp_setting()

        populate_zone_limit_setting()

        parse_controller_network(config)

        if not options['testing']:
            populate_openstack_keypair()
            synchronize()

        logger.info('Finished parsing configuration.')

    def add_arguments(self, parser):
        parser.add_argument(
            '--file', help='The YAML config file to parse.', default='all')
        parser.add_argument(
            '--testing', help='Only populate testing data', default=False)
