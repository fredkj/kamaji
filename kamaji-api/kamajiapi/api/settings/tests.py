# -*- coding: utf-8 -*-
import logging

from .base import *

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

logging.basicConfig(level=logging.DEBUG)

CELERY_ALWAYS_EAGER = True

EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

TEST_APPS = (
    'django_jenkins',
)

INSTALLED_APPS += TEST_APPS


PROJECT_APPS = (
    'fabric',
    'shared',
    'user_management',
)


COVERAGE_EXCLUDES_FOLDERS = [
    'fabric/migrations/*',
    'user_management/migrations/*',
]

JENKINS_TASKS = (
    'django_jenkins.tasks.run_pep8',
    'django_jenkins.tasks.run_pylint',
)

BUILD_DATA_PATH = os.path.join(BASE_DIR, 'api/tests/test_build.json')
