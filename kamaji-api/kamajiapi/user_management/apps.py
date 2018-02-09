# -*- coding: utf-8 -*-
from django.apps import AppConfig


class AutoInitializedConfiguration(AppConfig):
    """
    Hooks up signal handlers.
    """
    name = 'user_management'
    verbose_name = 'User Mangement'

    def ready(self):
        # Import the signal handlers so they register themselves
        import user_management.signals.handlers

