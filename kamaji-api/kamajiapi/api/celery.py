# -*- coding: utf-8 -*-
from __future__ import absolute_import

import os

from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'api.settings.base')

from django.conf import settings

# Create a Celery app engine to run tasks
app = Celery('api')

# Discover which apps that are installed in the project and look for tasks.py
# These tasks.py contains Celery tasks
app.config_from_object('django.conf:settings')
app.autodiscover_tasks(lambda: settings.INSTALLED_APPS)
