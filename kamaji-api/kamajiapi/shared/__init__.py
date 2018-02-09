# -*- coding: utf-8 -*-
import os

# Set ANSIBLE_CONFIG before importing ansible modules
from django.conf import settings
os.environ["ANSIBLE_CONFIG"] = settings.ANSIBLE['paths']['config']
