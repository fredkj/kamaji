# -*- coding: utf-8 -*-

from shared.exceptions import IllegalFieldInFilter


class AllFieldsFilterBackend(object):
    """
    This filter backend allows basic filtering based on url query parameters.
    If an endpoint is called with /?type=instance&ip_address=10.192.17.2 the
    filter will more or less return a
    MyModel.objects.filter(type="instance", ip_address="10.192.17.2").
    """
    @staticmethod
    def __generate_field_error_message(invalid_fields, valid_fields):
        if len(invalid_fields) == 1:
            field_error_message = 'Invalid field in filter: "{0}". '.format(
                invalid_fields.pop(),
            )
        else:
            field_error_message = 'Invalid fields in filter: {0}. '.format(
                ', '.join(map(
                    lambda field_name: '"{0}"'.format(field_name),
                    invalid_fields
                ))
            )

        valid_fields_message = 'Valid fields are: {0}'.format(
            ', '.join(valid_fields)
        )

        return field_error_message + valid_fields_message

    @staticmethod
    def __extract_fields_from_model(model):
        result = {field.name for field in model._meta.get_fields()}

        if hasattr(model, 'OpenStackMeta'):
            result = result.union(model.OpenStackMeta.fields.keys())

        return result

    def filter_queryset(self, request, queryset, view):
        serializer = view.get_serializer(request)

        if hasattr(view, 'filter_fields'):
            valid_fields = view.filter_fields
        else:
            model_fields = self.__extract_fields_from_model(queryset.model)
            valid_fields = set(serializer.get_fields().keys()) & model_fields

        specified_fields = set(request.query_params.keys())
        invalid_fields = specified_fields - valid_fields

        if invalid_fields:
            raise IllegalFieldInFilter(
                self.__class__.__generate_field_error_message(
                    invalid_fields,
                    valid_fields
                )
            )

        return queryset.filter(**request.query_params.dict())
