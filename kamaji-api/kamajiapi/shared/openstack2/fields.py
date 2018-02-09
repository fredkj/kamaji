# -*- coding: utf-8 -*-
from django.core.exceptions import ValidationError
from django.core.validators import MaxLengthValidator


class RemoteField(object):
    """
    A field that when set on a OSModel subclass will be converted to a
    property with the getter and setter connected to the get_value resp.
    set_value methods.

    The self.field_name will be added by the OSModel metaclass.
    """

    def __init__(self,
                 source=None,
                 target=None,
                 read_only=False,
                 write_only=False,
                 mutable=True,
                 validators=None,
                 default=None,
                 unique=False):
        """
        :param source: The name of the resource field to use when getting
        a resource.
        :type source: str
        :param target: The name of the resource field to use then posting or
        updating a resource.
        :type target: str
        :param read_only: Only allow reading the field value.
        :type read_only: bool
        :param write_only: Only allow setting the field value.
        :type write_only: bool
        :param mutable: Allow updating the field value.
        :type mutable: bool
        :param validators: The validators to use when validating the field.
        :type validators: list
        :param default: The default value of the field.
        :param unique: Only allow unique values for this field.
        """
        if read_only and write_only:
            raise ValueError('A field cannot be read_only and write_only '
                             'at the same time.')
        self.mutable = mutable
        self.__source = source
        self.__target = target
        self.read_only = read_only
        self.write_only = write_only
        self.mutable = mutable
        self.validators = validators or []
        self.default = default
        self.unique = unique

    @property
    def source(self):
        return self.__source or self.field_name

    @property
    def target(self):
        return self.__target or self.field_name

    def set_value(self, instance, value):
        instance._values[self.source] = value

    def get_value(self, instance):
        try:
            return instance._values[self.source]
        except KeyError:
            return self.default

    def validate(self, value):
        """
        Validates the value and raises a models.ValidationError if it fails.
        :param value: The value to validate.
        :raises: models.ValidationError
        """
        for validator in self.validators:
            validator(value)


class RemoteReferenceField(RemoteField):
    """
    This field is intended to work with "*Ref"-fields in the OpenStack API,
    i.e. flavorRef and imageRef in the instance model. The model will append
    a "Ref" suffix to the field target name and (with the help of the OSModel)
    keep the input and output data between Kamaji and OpenStack consistent.

    """
    @property
    def target(self):
        return "{0}Ref".format(super(RemoteReferenceField, self).target)


class RemoteCharField(RemoteField):
    """
    A RemoteField that represents a string value.
    """
    def __init__(self, max_length, *args, **kwargs):
        self.max_length = max_length
        super(RemoteCharField, self).__init__(*args, **kwargs)
        self.validators.append(MaxLengthValidator(self.max_length))

    def validate(self, value):
        if not isinstance(value, basestring):
            raise ValidationError('Must be a string', code='invalid type')

        super(RemoteCharField, self).validate(value)


class RemoteStringEncodedIntField(RemoteField):
    """
    A RemoteField that represents an OpenStack string-encoded int value.
    """
    def __init__(self, *args, **kwargs):
        super(RemoteStringEncodedIntField, self).__init__(*args, **kwargs)

    def get_value(self, instance):
        value = super(RemoteStringEncodedIntField, self).get_value(instance)
        return int(value) if value else None

    def set_value(self, instance, value):
        str_value = str(value)
        super(RemoteStringEncodedIntField, self).set_value(instance, str_value)
