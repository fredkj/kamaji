# -*- coding: utf-8 -*-
from json import dumps, JSONEncoder

from django.core.management.base import BaseCommand
from rest_framework_swagger.docgenerator import DocumentationGenerator
from rest_framework_swagger.urlparser import UrlParser


class KamajiJSONEncoder(JSONEncoder):
    def default(self, o):
        # In case the serialization fails, return a string representation of
        # the object.

        return str(o)


class Command(BaseCommand):
    """ Generate a json representation of the Kamaji API following the Swagger
    specification. """
    help = 'Generate Swagger 1.2 compliant API documentation'

    def handle(self, *args, **options):
        generator = DocumentationGenerator()
        apis = UrlParser().get_apis(filter_path=None)

        print(dumps({
            'apiVersion': '',
            'swaggerVersion': '1.2',
            'basePath': 'http://localhost:8000',
            'resourcePath': '/',
            'apis': generator.generate(apis),
            'models': generator.get_models(apis)
        }, cls=KamajiJSONEncoder))