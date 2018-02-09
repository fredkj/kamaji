from rest_framework import serializers
from rest_framework.reverse import reverse

from shared.urlresolvers import get_uri_template


class StaticRelatedField(serializers.HyperlinkedRelatedField):
    def __init__(self, view_name):
        super(StaticRelatedField, self).__init__(
            view_name,
            read_only=True,
            source='*'
        )

    def get_url(self, obj, view_name, request, format):
        return reverse(view_name, request=request)


class URITemplateRelatedField(serializers.HyperlinkedIdentityField):
    """
    This field allows for using hyperlinked field that contain both assigned
    and templated arguments. For example, if we have the URL template
    ^project/(?P<id>[0-9]+)/memberships/(?P<username>[a-zA-Z]+)$, we could
    provide the link project/4711/memberships/{{username}} by instantiating
    this field like this:

    >>> URITemplateRelatedField(
            view_name='project_memberships',
            assigned_parameters={
                'project_id': 'id'
            },
            templated_parameters=('username', )
        )
    """
    def __init__(self,
                 view_name,
                 templated_parameters,
                 assigned_parameters=None):

        self.templated_parameters = templated_parameters
        self.assigned_parameters = assigned_parameters

        super(URITemplateRelatedField, self).__init__(
            view_name,
            read_only=True,
            source='*'
        )

    def get_url(self, obj, view_name, request, format):
        assigned_values = {
            key: getattr(obj, value)
            for key, value in self.assigned_parameters.items()
        }

        return get_uri_template(
            view_name,
            request,
            *self.templated_parameters,
            assigned_parameters=assigned_values
        )


class CustomAttributeRelatedField(serializers.HyperlinkedRelatedField):
    """
    Adds a 'link' field to a serializer based on the model of the field
    specified by the 'source_attr' parameter.
    """
    def __init__(self, view_name=None, source_attr=None, **kwargs):
        """

        :param view_name: The name of the view as specified in the url mapping.
        :param source_attr: The attribute on the serializer that contains the
        model that should be linked.
        :param kwargs: Passed on to __init__ of HyperlinkedRelatedField.
        """
        if not source_attr:
            raise ValueError('source_attr must be specified.')
        self.source_attr = source_attr
        super(CustomAttributeRelatedField, self).__init__(
            view_name=view_name, **kwargs)

    def get_attribute(self, instance):
        """
        Use the 'source_attr' instead of the field name for getting the
        attribute.
        :param instance: The instance of the original model.
        :return: The specified 'source_attr' of the instance.
        """
        return getattr(instance, self.source_attr)


class MultipleKeyHyperlinkedRelatedField(serializers.HyperlinkedRelatedField):
    """
    This field can be used to represent a link from an object to an endpoint
    in the API that is dependant on more than one url kwarg and therefore
    cannot be represented by a HyperlinkedIdentityField.

    The field is used by specifying the view name and the mapping between
    model fields and url kwargs.

    :Example:
    student_link = MultipleKeyHyperlinkedRelatedField('student_list', {
        'school': 'school_id',
        'class': 'class_id'
    })

    """
    def __init__(self,
                 view_name,
                 lookup_field_mapping,
                 static_field_mapping=None,
                 **kwargs):
        """
        :param view_name: The view name that should be used as the target of
        this relationship.
        :type view_name: str
        :param lookup_field_mapping: The mapping between instance variables
         and the url kwargs.
        :type lookup_field_mapping: dict
        :param static_field_mapping: Static mappings to perform, without
         picking values from a model.
        :type static_field_mapping: dict
        :param kwargs: Additional arguments to the relation that will be passed
        to the superclass.
        :type kwargs: dict
        """
        kwargs['read_only'] = True
        kwargs['source'] = '*'
        self.lookup_field_mapping = lookup_field_mapping
        self.static_field_mapping = static_field_mapping
        super(MultipleKeyHyperlinkedRelatedField, self).__init__(view_name,
                                                                 **kwargs)

    def get_url(self, obj, view_name, request, format):
        """
        Get the url for a specified view using instance variables for the
        given objects.

        :param obj: The object to extract view parameters from.
        :type obj: object
        :param view_name: The view to use
        :type view_name: str
        :param request: The incoming request
        :type request: HttpRequest
        :param format: Expected format of the response
        :type format: str
        :return: The identified link
        :rtype: str
        """
        url_kwargs = {
            url_kwarg: getattr(obj, field) for url_kwarg, field
            in self.lookup_field_mapping.items()
        }

        url_kwargs.update(self.static_field_mapping)

        return reverse(self.view_name,
                       kwargs=url_kwargs,
                       request=request,
                       format=format)
