# -*- coding: utf-8 -*-
from django.db import models


class KamajiModel(models.Model):
    """
    Abstract class that adds convenience methods and properties to the django :class:`django.db.models.Model`
    class. More specifically it adds a validate method that is executed before saving.
    """

    class Meta:
        abstract = True

    @property
    def is_created(self):
        return self.pk is not None

    def save(self, force_insert=False, force_update=False, using=None,
             update_fields=None, perform_validation=True):
        """:raises: :class:`django.core.exceptions.ValidationError` if the validation fails."""
        # Call full_clean on the model before calling save to force validation.
        if perform_validation:
            self.validate()

        super(KamajiModel, self).save(
            force_insert=force_insert,
            force_update=force_update,
            using=using,
            update_fields=update_fields
        )

    def validate(self):
        """
        Override this method in the child class to validate model instances
        before saving them.
        Subclasses should call the super validate method if it is overwritten.

        :raises: :class:`django.core.exceptions.ValidationError` if the validation fails.
        """
        self.full_clean()

    def validate_unique(self, exclude=None):
        """:raises: :class:`django.core.exceptions.ValidationError` if the validation fails."""
        super(KamajiModel, self).validate_unique(exclude=exclude)
