# -*- coding: utf-8 -*-
from shared.openstack2.exceptions import (
    OpenStackError, BadRequest, Unauthorized, AuthenticationError,
    ConflictError, MultipleObjectsReturned, EndpointNotFound, NotFoundError
)
from shared.openstack2.fields import RemoteField, RemoteReferenceField
from shared.openstack2.models import OSModel
from shared.openstack2.shortcuts import OSResourceShortcut

_exceptions = [
    'OpenStackError', 'AuthenticationError', 'ConflictError', 'NotFoundError',
    'OpenStackBadRequest', 'Unauthorized', 'MultipleObjectsReturned',
    'EndpointNotFound'
]

_classes = [
    'OSModel', 'RemoteField', 'RemoteReferenceField', 'OSResourceShortcut'
]

__all__ = _classes + _exceptions
