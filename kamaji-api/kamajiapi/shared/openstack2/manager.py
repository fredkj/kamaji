# -*- coding: utf-8 -*-

from django.core.exceptions import FieldError
from django.db import models


class OpenStackManager(models.Manager):
    def get_queryset(self):
        return OpenStackQuerySet(self.model, using=self._db)


class OpenStackSynchronizingManager(OpenStackManager):
    """Manager that synchronizes with OpenStack before each set retrieval."""
    def get_queryset(self):
        self.model.synchronize()
        return super(OpenStackSynchronizingManager, self).get_queryset()


class OpenStackQuerySet(models.QuerySet):
    def filter(self, *args, **kwargs):
        try:
            return super(OpenStackQuerySet, self).filter(*args, **kwargs)
        except FieldError:
            # This should include ALL fields (db fields also), but we don't
            # support manual assignment of db fields today, so better exclude
            # them.
            if not all([key in self.model.get_remote_fields()
                        for key in kwargs.keys()]):
                raise FieldError('Cannot resolve all keywords into fields')

            result = self._clone()

            for item in self.all():
                if not all([value == getattr(item, field)
                            for field, value in kwargs.items()]):

                    result = result.exclude(pk=item.pk)

            return result

    def get(self, *args, **kwargs):
        try:
            return super(OpenStackQuerySet, self).get(*args, **kwargs)
        except FieldError:
            matches = self.filter(*args, **kwargs)

            if len(matches) == 0:
                raise self.model.DoesNotExist(
                    '{0} matching query does not exist'.format(
                        self.model.__name__)
                )

            if len(matches) > 1:
                raise self.model.MultipleObjectsReturned(
                    'get() returned more than one {0} -- it returned {1}!'
                          .format(self.model.__name__, len(matches))
                )

            return matches[0]

    def delete(self):
        for item in self.all():
            item.delete()
        super(OpenStackQuerySet, self).delete()
