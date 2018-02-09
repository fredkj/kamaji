# -*- coding: utf-8 -*-
from rest_framework import status
from rest_framework.exceptions import APIException


def _format_ansible_details(messages):
    return ['{0}: {1}'.format(host, msg) for (host, msg) in messages.items()]


class KamajiApiException(APIException):
    """
    The base of all Kamaji Api Exceptions.
    """
    pass


class KamajiRemoteApiException(KamajiApiException):
    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    default_detail = 'Error when contacting remote resource.'


class KamajiRemoteTimeoutApiException(KamajiApiException):
    status_code = status.HTTP_408_REQUEST_TIMEOUT
    default_detail = 'Timeout when contacting remote resource.'


class KamajiRemoteConflictApiException(KamajiApiException):
    status_code = status.HTTP_409_CONFLICT
    default_detail = 'Remote resource already exists.'


class KamajiRemoteConnectionApiException(KamajiApiException):
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    default_detail = 'Connection failure that may be retried.'


class IncorrectSetupApiException(KamajiApiException):
    status_code = 422
    default_detail = 'The Kamaji Cloud is not correctly setup'


class KamajiApiBadRequest(KamajiApiException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = 'Not Allowed'


class Conflict(KamajiApiException):
    status_code = status.HTTP_409_CONFLICT
    default_detail = 'The request could not be completed due to a conflict ' \
                     'with the current state of the target resource.'


# Normal Exceptions #
class KamajiError(Exception):
    """The base exception for all Kamaji Errors."""
    default_message = 'Kamaji Error'

    def __init__(self, message=None, *args, **kwargs):
        if not message:
            message = self.default_message
        super(KamajiError, self).__init__(message, *args, **kwargs)


class IllegalPlaybookFormatError(KamajiError):
    """ Thrown when a malformed playbook is uploaded """
    pass


class ResourceInUseError(KamajiError):
    """
    Thrown when the user is trying to delete a resource that is in use.
    For example if the user tries to delete a layer when the layer
    is already added to a stack.
    """
    pass


class InvalidSSHKeyError(KamajiError):
    """
    Thrown when trying to create a KamajiUser with an invalid ssh key.
    """
    default_message = 'Invalid SSH Key'


class UnsupportedOperation(KamajiError):
    """
    Thrown when the user is trying to do something thatis not allowed.
    For example if the user is trying to remove a controller network.
    """
    pass


class OperationTimedOut(KamajiError):
    """
    Thrown when the API has waited longer than the defined threshold for an
    external system to perform an operation.
    """
    pass


class IllegalState(KamajiError):
    """
    Thrown when the user is trying to perform an action on a
    resource which can't be fulfilled due to the state of said resource.
    """
    pass


class UpdatesNotSupported(KamajiError):
    """
    Thrown when an update is initiated on a model which does not support
    updates.
    """
    default_message = 'Updates are not supported for this model'


# OpenStack Exceptions #
class KamajiOpenStackError(KamajiError):
    """
    The base exception for all OpenStack exceptions.
    """

    def __init__(self, message=None, status_code=None):
        """
        :param message: The message returned from OpenStack.
        :type message: basestring
        :param status_code: The HTTP status code returned by OpenStack.
        :type status_code: int
        """
        self.status_code = status_code
        super(KamajiOpenStackError, self).__init__(message)


class KamajiOpenStackNotFoundError(KamajiOpenStackError):
    pass


class KamajiOpenStackResourceError(KamajiOpenStackError):
    pass


class CouldNotAssignDNSName(KamajiOpenStackResourceError):
    pass


class KamajiInstanceCreationError(KamajiOpenStackResourceError):
    default_message = 'Failed to create a working instance.'


class KamajiInstanceSSHError(KamajiOpenStackError):
    pass


class UniqueConstraintViolation(KamajiOpenStackError):
    pass


class OpenStackBadRequest(KamajiOpenStackError):
    default_message = 'Bad Request'


# Ansible Exceptions
class AnsibleError(KamajiError):
    pass


class AnsibleHostsUnavailableError(AnsibleError):
    def __init__(self, unavailable_hosts=None):
        self.unavailable_hosts = unavailable_hosts
        if unavailable_hosts is None:
            super(AnsibleHostsUnavailableError, self).__init__(
                'Host(s) unavailable.'
            )
        else:
            super(AnsibleHostsUnavailableError, self).__init__(
                _format_ansible_details(unavailable_hosts))


class AnsiblePlaybookError(AnsibleError):
    pass


class IllegalFieldInFilter(KamajiError):
    pass
