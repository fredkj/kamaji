"""
Base settings file for environments.


DO NOT LOAD ME DIRECTLY!


"""

# Build paths inside the project like this: os.path.join(BASE_DIR, ...)
import os

import datetime
import raven

BASE_DIR = os.path.dirname(
    os.path.dirname(os.path.abspath(os.path.join(__file__, '../'))))

# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/1.8/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = 'wkmbw74zubfl$zey7mk)+lx%9pq$@3n9d9i$=lnhvb+r!-nlch'

ALLOWED_HOSTS = ['*']

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'filters': {
        'request': {
            '()': 'django_requestlogging.logging_filters.RequestFilter',
        },
    },
    'formatters': {
        'verbose_user': {
            'format': "[%(asctime)s] %(levelname)s [%(name)s:%(lineno)s] "
                      "[User:%(username)s] %(message)s"
        },
        'verbose': {
            'format': "[%(asctime)s] %(levelname)s [%(name)s:%(lineno)s] "
                      "%(message)s"
        }
    },
    'handlers': {
        'console_request': {
            'class': 'logging.StreamHandler',
            'level': 'DEBUG',
            'formatter': 'verbose_user',
            'filters': ['request']
        },
        'console': {
            'class': 'logging.StreamHandler',
            'level': 'DEBUG',
            'formatter': 'verbose'
        }
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'propagate': True,
            'level': 'DEBUG'
        },
        'django.request': {
            'handlers': ['console'],
            'propagate': False,
            'level': 'DEBUG',
        },
        'django.template': {
            'handlers': ['console'],
            'propagate': False,
            'level': 'INFO',
        },
        'django.db.backends': {
            'handlers': ['console'],
            'propagate': False,
            'level': 'INFO',  # Set this to DEBUG to see db queries
        },
        'network': {
            'handlers': ['console'],
            'level': 'DEBUG',
        },
        'shared': {
            'handlers': ['console'],
            'level': 'DEBUG',
            'propagate': False
        },
        'fabric': {
            'handlers': ['console'],
            'level': 'DEBUG',
            'propagate': False
        },
        'user_management': {
            'handlers': ['console'],
            'level': 'DEBUG'
        },
        'user_management.permissions': {
            'handlers': ['console_request'],
            'level': 'DEBUG',
            'propagate': False
        },
        'requests': {
            'handlers': ['console'],
            'level': 'ERROR',
            'propagate': False
        },
        'api': {
            'handlers': ['console'],
            'level': 'DEBUG',
            'propagate': False
        },
        'paramiko.transport': {
            'handlers': ['console'],
            'propagate': True,
            'level': 'WARNING'
        }
    }
}

# Application definition

INSTALLED_APPS = (
    'django_requestlogging',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'lettuce.django',
    'fabric',
    'user_management',
    'api',
    'raven.contrib.django.raven_compat'
)

MIDDLEWARE_CLASSES = (
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.auth.middleware.SessionAuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django_requestlogging.middleware.LogSetupMiddleware'
)

ROOT_URLCONF = 'api.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [os.path.join(BASE_DIR, 'api/templates')]
        ,
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

MEDIA_ROOT = BASE_DIR + '/api/templates'

MEDIA_URL = '/statics/'

WSGI_APPLICATION = 'api.wsgi.application'

REST_FRAMEWORK = {
    'DEFAULT_PERMISSION_CLASSES': (
        'user_management.permissions.IsAuthenticatedOrOptions',
        'user_management.permissions.HasGroupAccessOrOptions'
    ),
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework.authentication.BasicAuthentication',
        'rest_framework.authentication.SessionAuthentication',
        'rest_framework_jwt.authentication.JSONWebTokenAuthentication'
    ),
    'EXCEPTION_HANDLER':
        'shared.view_exception_handler.kamaji_exception_handler',
    'DEFAULT_FILTER_BACKENDS': (
        'shared.filter_backend.AllFieldsFilterBackend',
    )
}
LOGIN_REDIRECT_URL = '/'


# Database
# https://docs.djangoproject.com/en/1.8/ref/settings/#databases

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': os.path.join(BASE_DIR, 'db.sqlite3'),
    }
}

# Internationalization
# https://docs.djangoproject.com/en/1.8/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_L10N = True

USE_TZ = True

# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/1.8/howto/static-files/

STATIC_URL = '/static/'

# Ansible
ANSIBLE_PATH = os.path.join(BASE_DIR, 'shared/ansible')
ANSIBLE = {
    'paths': {
        'config': ANSIBLE_PATH + '/ansible.cfg',
        'inventory': ANSIBLE_PATH + '/inventory',
        'playbook': ANSIBLE_PATH + '/playbooks',
    },
    'keys': {
        'inventory': ANSIBLE_PATH + '/keys/inventory.key',
        'private': ANSIBLE_PATH + '/keys/private.key',
        'compute': ANSIBLE_PATH + '/keys/compute.key',
    },
}

OPENSTACK_INSTANCE_KEY_NAME = 'openstack_instance_key'
PROVISIONING_KEY = BASE_DIR + '/provisioning/ansible/keys/private.key'

FRONTEND_PASSWORD_RESET_PATH = '{{ hostname }}/me/reset_password/?' \
                               'token={{ token }}&' \
                               'email={{ user.email }}'

EMAIL_BACKEND = 'shared.email_backend.KamajiEmailBackend'

JWT_AUTH = {
    'JWT_ENCODE_HANDLER':
    'rest_framework_jwt.utils.jwt_encode_handler',

    'JWT_DECODE_HANDLER':
    'rest_framework_jwt.utils.jwt_decode_handler',

    'JWT_PAYLOAD_HANDLER':
    'rest_framework_jwt.utils.jwt_payload_handler',

    'JWT_PAYLOAD_GET_USER_ID_HANDLER':
    'rest_framework_jwt.utils.jwt_get_user_id_from_payload_handler',

    'JWT_RESPONSE_PAYLOAD_HANDLER':
    'user_management.permissions.jwt_response_payload_handler',

    'JWT_SECRET_KEY': SECRET_KEY,
    'JWT_ALGORITHM': 'HS256',
    'JWT_VERIFY': True,
    'JWT_VERIFY_EXPIRATION': True,
    'JWT_LEEWAY': 30,
    'JWT_EXPIRATION_DELTA': datetime.timedelta(hours=24),
    'JWT_AUDIENCE': None,
    'JWT_ISSUER': None,

    'JWT_ALLOW_REFRESH': True,
    'JWT_REFRESH_EXPIRATION_DELTA': datetime.timedelta(days=7),

    'JWT_AUTH_HEADER_PREFIX': 'JWT',
}

# Test timeout in seconds for connection tests that allows specific timeouts
CONNECTION_TEST_TIMEOUT = 4

# OpenStack Keystone
KEYSTONE_AUTH_TEMPLATE = 'http://keystone.service.$url:5000/v3/auth/tokens'
KEYSTONE_USER_DOMAIN_NAME = 'default'

POWERDNS_PORT = 8081
POWERDNS_SCHEMA = 'http'

DEFAULT_ZONE_LIMIT = 6

LAYER_PATH = os.path.join(BASE_DIR, 'playbooks')

# Sentry
RAVEN_CONFIG = {}

INTEGRATION_TEST_URL = 'http://10.192.6.4/api'

LETTUCE_APPS = tuple(set(INSTALLED_APPS) & set(os.listdir('.')))

BUILD_DATA_PATH = os.path.join(BASE_DIR, 'build.json')
