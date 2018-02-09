# -*- coding: utf-8 -*-

from django.core.exceptions import ValidationError
import fabric.models


def validate_single_controller_network(network_type):
    """
    Validate that there is no existing controller network.
    """
    if (network_type == fabric.models.PhysicalNetwork.CONTROLLER_NETWORK and
            fabric.models.PhysicalNetwork.controller_networks.count() > 0):
        raise ValidationError(
            'A controller network is already configured.'
        )
