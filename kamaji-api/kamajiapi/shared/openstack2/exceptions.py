# -*- coding: utf-8 -*-
from shared.exceptions import KamajiError


class OpenStackError(KamajiError):
    default_message = 'Openstack Error'


class AuthenticationError(OpenStackError):
    default_message = 'Could not authenticate towards OpenStack.'
    project_message_template = 'Could not authenticate towards OpenStack ' \
                               'project \'{0}\''

    def __init__(self, project=None):
        if project is None:
            super(AuthenticationError, self).__init__()
        else:
            super(AuthenticationError, self).__init__(
                self.project_message_template.format(project)
            )


class ConflictError(OpenStackError):
    default_message = 'Conflict'


class NotFoundError(OpenStackError):
    default_message = 'Not Found'


class BadRequest(OpenStackError):
    default_message = 'Bad Request'


class Unauthorized(OpenStackError):
    default_message = 'Unauthorized'


class MultipleObjectsReturned(OpenStackError):
    default_message = 'The filtered GET request returned more than one item'


class EndpointNotFound(OpenStackError):
    pass
