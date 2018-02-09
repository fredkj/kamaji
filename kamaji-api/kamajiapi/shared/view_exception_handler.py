# -*- coding: utf-8 -*-
import logging

import django.core.exceptions
from rest_framework.response import Response
from rest_framework.views import exception_handler

from shared import exceptions as kamaji_exceptions
from shared.openstack2 import exceptions as os_exceptions

logger = logging.getLogger(__name__)


def kamaji_exception_handler(exc, context):
    """
    Handle errors in views a little more gracefully than Django REST's default.

    In case the default exception handle doesn't come up with a response
    (returns None) we'll try to find a response depending on the passed
    exception.

    :param exc: The raised exception
    :type exc: Exception
    :param context: Context of the performed request
    :type context: dict
    :return: Appropriate response depending on the passed exception.
    :rtype: Response or None
    """
    response = exception_handler(exc, context)

    if response is None:
        if isinstance(exc, kamaji_exceptions.KamajiOpenStackNotFoundError):
            response = Response(status=404, data=exc.message)

        elif isinstance(exc, (
                kamaji_exceptions.ResourceInUseError,
                kamaji_exceptions.UniqueConstraintViolation,
                kamaji_exceptions.InvalidSSHKeyError,
                kamaji_exceptions.UnsupportedOperation,
                kamaji_exceptions.UpdatesNotSupported,
                kamaji_exceptions.IllegalFieldInFilter
        )):
            response = Response(status=400, data=exc.message)

        elif isinstance(exc, (
                kamaji_exceptions.CouldNotAssignDNSName,
                kamaji_exceptions.KamajiInstanceCreationError,
                kamaji_exceptions.OperationTimedOut
        )):
            logger.exception(exc.message)
            response = Response(status=500, data=exc.message)

        # Catch all model validation errors
        elif isinstance(exc, django.core.exceptions.ValidationError):
            # The validation error from Django can have messages in different
            # form. We try to get the message dict first, if that doesn't work
            # out, let's go for the message field.
            try:
                message = exc.message_dict
            except AttributeError:
                message = exc.message

            response = Response(status=400, data=message)

        # OpenStack exceptions
        elif isinstance(exc, os_exceptions.BadRequest):
            response = Response(status=400, data=exc.message)

    return response
