# -*- coding: utf-8 -*-
from django.db import models


class FilteredManager(models.Manager):
    """
    Provides a filtered object manager that returns only those objects matching the provided filter.
    """
    def __init__(self, filters=None, *args, **kwargs):
        self.filters = filters or {}
        super(FilteredManager, self).__init__(*args, **kwargs)

    def get_queryset(self):
        return super(FilteredManager, self).get_queryset().filter(
            **self.filters
        )
