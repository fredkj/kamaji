# -*- coding: utf-8 -*-

import logging
from collections import namedtuple
from functools import partial
from string import Template
from urlparse import urljoin

import requests
from django.conf import settings

from fabric.models.models_credentials import Credential
from fabric.models.models_settings import Setting
from shared.openstack2.exceptions import (
    AuthenticationError, OpenStackError, BadRequest, NotFoundError,
    ConflictError, Unauthorized, EndpointNotFound
)

logger = logging.getLogger(__name__)


class OSSession(object):
    """
    Provides functionality to post, get, put, patch and delete
    Open Stack resources.
    The class is as lazy as can be so creating an instance of this class
    will not do any heavy lifting.
    """
    def __init__(self, system, resource, project=None):
        """
        :param project: The Open Stack project id to authenticate against.
        :type project: str
        """
        self.project = project
        self.__prepared_request = partial(
            self.__request,
            system=system,
            resource=resource
        )

    @property
    def _session(self):
        return SessionCollection.get_session(self.project)

    @property
    def _endpoints(self):
        return SessionCollection.get_endpoints(self.project)

    def get(self, path=None):
        return self.__prepared_request('GET', path=path)

    def post(self, path=None, **kwargs):
        return self.__prepared_request('POST', path=path, **kwargs)

    def delete(self, path=None):
        return self.__prepared_request('DELETE', path=path)

    def update(self, method, path=None, **kwargs):
        if method not in ('PATCH', 'PUT'):
            raise ValueError('method')
        return self.__prepared_request(method, path=path, **kwargs)

    def __request(self, method, system, resource, path=None, **kwargs):
        # If the path is a single item, turn it into a tuple
        if path is None:
            path = []
        elif (isinstance(path, basestring) or
              not isinstance(path, (tuple, list))):
            path = (path,)

        url = self.__get_complete_endpoint(system, resource, *path)
        try:
            response = self._session.request(method, url, **kwargs)
            self.__log_response(response, method, url, kwargs)

            if response.status_code == 401:
                # The session has expired
                SessionCollection.refresh_session(self.project)
                response = self._session.request(method, url, **kwargs)
                self.__log_response(response, method, url, kwargs)

            return self.__raise_on_failure(response)
        except requests.exceptions.RequestException as e:
            raise OpenStackError(e.message)

    @classmethod
    def __log_response(cls, response, method, url, kwargs):
        logger.debug(
            '%s %s %i %i', method, url, response.status_code,
            response.elapsed.total_seconds() * 1000
        )
        if 'json' in kwargs:
            logger.debug('Request: {0}'.format(kwargs['json']))
        elif 'data' in kwargs:
            logger.debug('Request: {0}'.format(kwargs['data']))

        logger.debug('Response Text: {0}'.format(response.text))

    def __get_complete_endpoint(self, system, *path):
        """
        Get the endpoint for the specified system and sub-paths.
        :param system: The system to retrieve the endpoint for.
        :type system: str
        :param path: The paths to append to the original endpoint.
        :type path: list
        :return: The complete endpoint for the specified system with all
        paths appended.
        :rtype: str
        """
        try:
            url = self._endpoints[system] + '/'
            url_parts = [str(part) for part in path if part is not None]
            return urljoin(url, '/'.join(url_parts))
        except KeyError:
            raise EndpointNotFound(
                'No endpoint for system {0}, existing endpoints are {1}'
                .format(system, self._endpoints.keys())
            )

    @staticmethod
    def __raise_on_failure(response, failure_threshold=400):
        """
        Parse the response and raise exceptions if it describes an error.
        :param response: A response from Open Stack,
        :type response: requests.Response
        :param failure_threshold: Minimum threshold to raise exceptions.
        :type failure_threshold: int
        :return: The response object unchanged.
        :rtype: requests.Response
        """
        if response.status_code >= failure_threshold:
            logger.error(response.text)
            if response.status_code == 400:
                raise BadRequest(response.text)
            if response.status_code == 401:
                raise Unauthorized(response.text)
            if response.status_code == 404:
                raise NotFoundError(response.text)
            if response.status_code == 409:
                raise ConflictError(response.text)
            raise OpenStackError(response.text)
        return response


class SessionCollection(object):
    """
    Provides functionality to retrieve an authorized session for Open Stack
    and all it's endpoints.
    Caches authorized sessions and endpoints to minimize requests.
    """

    SessionInfo = namedtuple('SessionInfo', ['session', 'endpoints'])

    SESSIONS = {}

    @classmethod
    def get_endpoints(cls, project):
        """
        Get the endpoints associated to a specific Open Stack project id.
        :param project: Open Stack project id to get endpoints for.
        :type project: str
        :return: The endpoint for the specified project.
        :rtype: str
        """
        try:
            return cls.SESSIONS[project].endpoints
        except KeyError:
            cls.refresh_session(project)
            return cls.SESSIONS[project].endpoints

    @classmethod
    def get_session(cls, project):
        """
        Get an authorized session for Open Stack either for the complete api
        or scoped to a project.
        :param project: Open Stack project id to authenticate against.
        :type project: str
        :return: An authorized session for the specified project.
        :rtype: requests.session
        """
        try:
            return cls.SESSIONS[project].session
        except KeyError:
            cls.refresh_session(project)
            return cls.SESSIONS[project].session

    @classmethod
    def refresh_session(cls, project):
        cls.SESSIONS[project] = cls.__create_session_info(project)

    @classmethod
    def __create_session_info(cls, project):
        """
        Create a new authorized session with Open Stack scoped to the
        specified project.
        :param project: Open Stack project id to authenticate against.
        :type project: str
        :return: An authorized session scoped to the specified project and
        all its endpoints.
        :rtype: requests.Session, dict
        """
        logger.debug('Creating a new session for project %s.', project)
        url = cls.__get_auth_url()
        data = cls.__get_auth_data(project)

        session = requests.Session()
        response = session.post(url, json=data)

        if response.status_code == 401:
            raise AuthenticationError(project)

        token = response.headers['x-subject-token']
        session.headers.update({'X-Auth-Token': token})

        return cls.SessionInfo(session, cls.__parse_endpoints(response))

    @classmethod
    def __parse_endpoints(cls, auth_response):
        """
        Parses and retrieves complete versions for all
        endpoints described in the response.
        :param auth_response: The response from a Open Stack authentication
        request.
        :type auth_response: dict
        :return: Complete versions of all Open Stack endpoints described in
        the response indexed by system.
        :rtype: dict
        """
        get_public_interface = partial(
            cls.__get_item,
            key='interface',
            value='public'
        )

        endpoints = {
            service['type']: get_public_interface(service['endpoints'])['url']
            for service in auth_response.json()['token']['catalog']
            }

        versioned_endpoints = {
            system: cls.__retrieve_versioned_endpoint(endpoint)
            for (system, endpoint) in endpoints.items()
            }

        return versioned_endpoints

    @classmethod
    def __get_auth_url(cls):
        """
        Get the authentication url for the Open Stack service.
        :return: Authentication url.
        :rtype: str
        """
        return Template(settings.KEYSTONE_AUTH_TEMPLATE).substitute(
            url=Setting.objects.get(setting='DomainSetting').domain
        )

    @classmethod
    def __get_auth_data(cls, project):
        """
        Get the authentication data to use for authenticating against
        Open Stack.
        :param project The Open Stack project id to authenticate with.
        :type project: str or None
        :return: A complete authentication request body.
        :rtype: dict
        """
        credentials = Credential.get_credential(Credential.OPENSTACK_ADMIN)
        auth_data = {
            "auth": {
                "identity": {
                    "methods": [
                        "password"
                    ],
                    "password": {
                        "user": {
                            "name": credentials.username,
                            "password": credentials.password,
                            "domain": {
                                "name": settings.KEYSTONE_USER_DOMAIN_NAME
                            }
                        }
                    }
                }
            }
        }
        if project:
            auth_data["auth"]["scope"] = {
                "project": {
                    "id": project
                }
            }
        return auth_data

    @classmethod
    def __retrieve_versioned_endpoint(cls, endpoint):
        """
        Query endpoints and parse the versioned url of the CURRENT version
        from the result if the status_code is 300: Multiple Choices...
        or if the status_code is 200 in case of neutron. *sigh*
        :param endpoint: The endpoint to query.
        :return: The versioned url with status CURRENT.
        """
        try:
            response = requests.get(endpoint)
        except requests.exceptions.RequestException:
            message = 'Error when retrieving versioned endpoint ' \
                      'at {0}.'.format(endpoint)
            logger.exception(message)
            raise OpenStackError(message)

        get_current = partial(
            cls.__get_item,
            key='status',
            value='CURRENT'
        )

        get_self = partial(
            cls.__get_item,
            key='rel',
            value='self'
        )

        if response.status_code in (300, 200):
            json_response = response.json()
            try:
                current = get_current(json_response['versions'])
                link = get_self(current['links'])
                return link['href']
            except KeyError:
                pass
        return endpoint

    @staticmethod
    def __get_item(items, key, value):
        """
        Retrieve the item from the collection that has a key with the
        specified value.
        :param items: Collection to search.
        :type items: list
        :param key: The key to check.
        :type key: str
        :param value: The value to compare against.
        :type value: any
        :return: The first item from the collection where item.key == value.
        :rtype: any
        """
        try:
            filtered = [x for x in items if x[key] == value]
            return filtered[0]
        except IndexError:
            raise OpenStackError(
                'No item with {0} for {1}'.format(value, key)
            )
