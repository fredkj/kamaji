# -*- coding: utf-8 -*-
from shared.openstack2.exceptions import NotFoundError, MultipleObjectsReturned
from shared.openstack2.sessions import OSSession


class OSResourceShortcut(object):
    """
    Provides a shortcut to OpenStack resources without specifying a model
    and without having to create the resource locally beforehand.
    """

    PUT = 'PUT'
    UPDATE = 'PATCH'

    def __init__(self, system, resource, path=None, project=None):
        self.path = path
        self.session = OSSession(system, resource, project)

    @staticmethod
    def __get_inner_resource(response):
        resources = response.json()
        if isinstance(resources, dict):
            return resources[resources.keys()[0]]
        return resources

    def get(self, **filters):
        resource = self.__get_inner_resource(self.session.get(self.path))

        # Lists are not filtered
        if len(filters) == 0:
            return resource

        matches = self.__filter(resource, **filters)
        if len(matches) == 0:
            raise NotFoundError('No item match for {0}'.format(filters))

        if len(matches) > 1:
            raise MultipleObjectsReturned(
                'Filtered GET returned more than one resource for filters '
                '{0} -- it returned {0}'.format(filters, len(matches)))

        return matches[0]

    def update(self, method, **kwargs):
        self.session.update(method, self.path, **kwargs)

    def post(self, **kwargs):
        return self.__get_inner_resource(
            self.session.post(self.path, **kwargs)
        )

    def delete(self):
        return self.session.delete(self.path)

    @staticmethod
    def __filter(resources, **filters):
        """
        Returns a list of resources filtered by the conditions provided as the
        arguments.

        Example::
            >>> for flavor in Flavor.objects.filter(is_public=True):
            ...     print(flavor.name)
            ...
            m2.mega
            m1.tiny
            m1.small
            m1.medium
            m1.large
            m1.nano
            m1.xlarge
            m1.micro

        :param conditions: The criteria to filter by
        :type conditions: dict
        :return: The filtered list of resources
        :rtype: list
        """
        def match_element(element):
            for key, value in filters.items():
                if key not in element or not element[key] == value:
                    return False

            return True

        return [item for item in resources if match_element(item)]
