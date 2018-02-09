# -*- coding: utf-8 -*-
import copy
from functools import partial

from django.core import exceptions
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models.base import ModelBase

from shared.models import KamajiModel
from shared.openstack2.fields import RemoteField, RemoteReferenceField
from shared.openstack2.manager import OpenStackManager
from shared.openstack2.sessions import OSSession


class KamajiRemoteModel(KamajiModel):
    """
    Abstract class that adds methods and properties related to remote
    resource manipulation to the deriving :class:`shared.models.KamajiModel` class .
    """

    class Meta:
        abstract = True

    def _prune_remote_fields(self, **kwargs):
        """
        Removes all references to remote fields in the supplied dict so a call
        to the django method super().save() can be made without django
        complaining.

        :param kwargs: The dict to clean of references.
        :type kwargs: dict
        :return: A copy of dict with all references to remote fields removed.
        :rtype: dict
        """
        try:
            update_fields = [field for field in kwargs['update_fields']
                             if field not in self.get_remote_fields()]
            local_kwargs = copy.deepcopy(kwargs)
            local_kwargs['update_fields'] = update_fields
            return local_kwargs
        except KeyError:
            return kwargs

    @classmethod
    def get_remote_sources(cls):
        """
        Return a mapping of the model name and the source name of the field in
        OpenStack.

        :return: A mapping of model name/source name
        :rtype: dict
        """
        return {
            field_name: field.source
            for field_name, field in cls.OpenStackMeta.fields.items()
            if field.write_only is False
        }

    @classmethod
    def get_remote_targets(cls):
        """
        Return a mapping of the model name and the target name of the field in
        OpenStack.

        :return: A mapping of model name/target name
        :rtype: dict
        """
        return {
            field_name: field.target
            for field_name, field in cls.OpenStackMeta.fields.items()
            if field.read_only is False
        }

    @classmethod
    def get_remote_mutable_targets(cls):
        """
        Return a mapping of the model name and the target name of the field in
        OpenStack for all editable fields.

        :return: Mapping of model name -> target name
        :rtype: dict
        """
        return {
            field_name: field.target
            for field_name, field in cls.OpenStackMeta.fields.items()
            if not field.read_only and field.mutable
        }

    @classmethod
    def get_remote_fields(cls):
        return cls.OpenStackMeta.fields.keys()

    @classmethod
    def synchronize(cls):
        """
        Synchronize this model with OpenStack by retrieving all resources from
        OpenStack and create local entries for those that have none.
        """
        # Make sure we are not already in the middle of syncing to avoid
        # perpetual recursion because of filter() and all() calls during the
        # model validation forced by the save() call.
        if not cls.OpenStackMeta._is_syncing:
            try:
                cls.OpenStackMeta._is_syncing = True
                _, resources = OSSession(
                    cls.OpenStackMeta.service,
                    cls.OpenStackMeta.resource
                ).get().json().popitem()
                for resource in resources:
                    try:
                        instance = cls(openstack_id=resource['id'])
                        super(KamajiRemoteModel, instance).save()
                    except exceptions.ValidationError as e:
                        # If there's already a model with this OpenStack id,
                        # don't create another one.
                        # TODO: You also get a validation error if you have
                        # local fields that cannot be null.
                        pass
            finally:
                cls.OpenStackMeta._is_syncing = False

    def validate(self):
        errors = {}
        for field_name, field in self.OpenStackMeta.fields.items():
            try:
                value = getattr(self, field_name)
                if value is not None:
                    field.validate(value)
            except ValidationError as e:
                errors[field_name] = e

        if len(errors) > 0:
            raise ValidationError(errors)

        super(KamajiRemoteModel, self).validate()

    def validate_unique(self, exclude=None):
        """
        Checks uniqueness for all fields marked as 'unique' by looping through
        all existing model instances and checking for equality.

        :param exclude: List of fields to exclude from the check.
        :type exclude: list
        """
        if self.is_created:
            items = self.__class__.objects.exclude(id=self.id)
        else:
            items = self.__class__.objects.all()

        errors = {}

        exclude = exclude or []
        fields = {name: field for name, field in
                  self.OpenStackMeta.fields.items() if name not in exclude}

        for field_name, field in fields.items():
            if field.unique:
                for item in items:
                    other_value = getattr(item, field_name)
                    value = getattr(self, field_name)
                    if other_value == value:
                        errors[field_name] = 'Must be unique.'
                        break

        if len(errors) > 0:
            raise ValidationError(errors)

        super(KamajiRemoteModel, self).validate_unique(exclude=exclude)


class OSMetaModel(ModelBase):
    """
    Metaclass that converts all instance variables of :class:`RemoteField`
    into properties whose setters and getters are bound to the set_value
    resp. get_value of the field.
    """
    def __init__(cls, name, bases, attributes):
        """
        :param name: The name of the class being initialized.
        :type name: basestring
        :param bases: The baseclasses of the class being initialized.
        :type bases: tuple
        :param attributes: The class attributes.
        :type attributes: dict
        """
        # Don't try to convert the baseclass OSModel
        if name is not 'OSModel':
            if not hasattr(cls, 'OpenStackMeta'):
                raise Exception('OSModel subclass missing OpenStackMeta.')

            cls.OpenStackMeta.fields = {}

            reserved_fields = (cls._meta.pk.name, 'pk')

            for property_name in attributes:
                try:
                    property_ = getattr(cls, property_name)
                    if isinstance(property_, RemoteField):
                        # Don't allow models to overwrite Django's
                        # auto-generated fields
                        if property_name in reserved_fields:
                            raise Exception(
                                'Model {0} may not override reserved field '
                                '\'{1}\'.'.format(name, property_name))

                        field = property_
                        field.field_name = property_name

                        setattr(cls, property_name, property(
                            field.get_value,
                            field.set_value
                        ))
                        cls.OpenStackMeta.fields[property_name] = field

                except AttributeError:
                    pass

            if not hasattr(cls.OpenStackMeta, 'update_method'):
                cls.OpenStackMeta.update_method = OSModel.PUT
            if not hasattr(cls.OpenStackMeta, 'update_headers'):
                cls.OpenStackMeta.update_headers = {}

            # Signifies whether the model is in the process of syncing with OS
            cls.OpenStackMeta._is_syncing = False

        super(OSMetaModel, cls).__init__(name, bases, attributes)


class OSModel(KamajiRemoteModel):
    """
    Baseclass for all OpenStack models.
    Requires any subclasses to implement an inner class called OpenStackMeta
    that holds info about the OpenStack resource it is connected to.
    Stores a local id and the openstack_id in the database and the rest in the
    OpenStack backend using the OpenStack rest api.

    Any instance variables of :class:`RemoteField` on the subclass will be
    converted to properties with the getter and setter connected
    to the get_value resp. set_value of the :class:`RemoteField`.
    The RemoteFields stores the actual values in the _values dict of this
    class.
    The actual :class:`RemoteField` instances are stored in the OpenStackMeta.fields
    dict.
    See :class:`OSMetaModel` for the logic of changing fields to properties.
    """
    PATCH = 'PATCH'
    POST = 'POST'
    PUT = 'PUT'

    __metaclass__ = OSMetaModel

    openstack_id = models.CharField(max_length=40, unique=True, blank=True)
    objects = OpenStackManager()

    class Meta:
        abstract = True

    @property
    def _openstack_resource_label(self):
        return self.OpenStackMeta.resource[:-1]

    @property
    def _session(self):
        return OSSession(
            self.OpenStackMeta.service,
            self.OpenStackMeta.resource,
            self._remote_project_id
        )

    def __init__(self, *args, **kwargs):
        # The actual values behind the dynamically assigned properties,
        # manipulated by the RemoteField instances.
        self._values = {}

        if kwargs:
            remote_kwargs = {field: value for field, value in kwargs.items()
                             if field in self.OpenStackMeta.fields.keys()}
            for field, value in remote_kwargs.items():
                setattr(self, field, value)
                kwargs.pop(field)

        super(OSModel, self).__init__(*args, **kwargs)

        if args:
            self.openstack_id = args[1]
            self.refresh_from_openstack()

    def _get_openstack_resource(self, openstack_id):
        openstack_resource = self._session.get(openstack_id).json()
        return openstack_resource[self._openstack_resource_label]

    @property
    def _remote_project_id(self):
        """
        Get the project id for the resource that this model represents. This
        property will be overridden by models that applies a project scope. For
        models that are not using project scoping, this method will return
        None, making the connector fetching them through the default admin project.

        :return: OpenStack project id for this resource.
        :rtype: string
        """
        return None

    def refresh_from_openstack(self):
        """
        Update all fields in the model with fresh values from OpenStack.
        Calling this method will reset any local changes to the model that
        has not been saved.
        """
        remote_object = self._get_openstack_resource(self.openstack_id)

        for field_name, source in self.get_remote_sources().items():
            field = self.OpenStackMeta.fields[field_name]
            if source in remote_object:
                field_value = remote_object[source]

                if isinstance(field, RemoteReferenceField) \
                        and isinstance(field_value, dict):
                    field_value = field_value['id']

                setattr(self, field_name, field_value)

    def _action(self, action_type, **arguments):
        self._session.post(path=(self.openstack_id, 'action'), json={
            action_type: arguments
        })

    def _get_save_parameters(self, **kwargs):
        """
        Get the parameters to use as the json argument when calling the
        update method.
        :param kwargs: The unchanged kwargs as they were passed to the save
        method.
        :type kwargs: dict
        :return: A dict with one index for the resource label containing the
        parameters.
        :rtype: dict
        """
        if self.is_created:
            remote_update_fields = self.get_remote_mutable_targets()
            if self.OpenStackMeta.update_method == self.PATCH:
                try:
                    remote_update_fields = [
                        field for field in kwargs['update_fields']
                        if field in self.get_remote_fields()]
                except KeyError:
                    # update_fields was not specified
                    pass
        else:
            remote_update_fields = self.get_remote_targets()

        fields = {
            target: getattr(self, field)
            for field, target in remote_update_fields.items()
            if getattr(self, field) is not None
        }

        return {self._openstack_resource_label: fields}

    def _get_openstack_id(self, resource):
        return resource.json()[self._openstack_resource_label]['id']

    def save(self, **kwargs):
        """Validate the model before saving"""
        self.validate()

        if self.is_created:
            update_method = partial(
                self._session.update,
                self.OpenStackMeta.update_method,
                path=self.openstack_id,
                headers=self.OpenStackMeta.update_headers
            )
        else:
            update_method = self._session.post

        resource = update_method(json=self._get_save_parameters())

        self.openstack_id = self._get_openstack_id(resource)

        # Don't perform validation again as we already did that earlier.
        super(OSModel, self).save(
            perform_validation=False,
            **self._prune_remote_fields(**kwargs)
        )

    def delete(self, **kwargs):
        self._session.delete(self.openstack_id)
        return super(OSModel, self).delete(**kwargs)
