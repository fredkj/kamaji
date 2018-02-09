import json
import logging
import os

from django.apps import AppConfig
from django.conf import settings

import api

logger = logging.getLogger(__name__)


class AutoInitializedConfiguration(AppConfig):
    name = 'api'
    verbose_name = "Api"

    def ready(self):
        """
        Load git commit data from JSON file and store in api.__commit__
        variable.
        """
        if os.path.isfile(settings.BUILD_DATA_PATH):
            try:
                with open(settings.BUILD_DATA_PATH) as json_file:
                    data = json.load(json_file)
                    api.__commit__ = data['git_short']
                    logger.info('Loading build data from {0}'.format(
                        settings.BUILD_DATA_PATH
                    ))
            except ValueError:
                logger.error('Can not decode the build data from {0}'.format(
                    settings.BUILD_DATA_PATH
                ))
            except KeyError as e:
                logger.error(
                    'Could not find `{0}` key in the build config'.format(
                        e.args[0]
                    )
                )
        else:
            logger.info('Can not find the build data at {0}'.format(
                settings.BUILD_DATA_PATH
            ))
