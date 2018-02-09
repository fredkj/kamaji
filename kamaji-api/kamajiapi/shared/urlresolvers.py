import urllib

from django.core import urlresolvers
from django.core.urlresolvers import NoReverseMatch


def get_uri_template(view_name, request, *placeholder_parameters, **kwargs):
    """
    Get a RFC 6570 compliant URI from doing a reverse lookup of url
    configurations. Accepts both assigned parameters, that will have an
    assigned value in the resulting template, and placeholder parameters that
    will be included in the template as {{parameter_name}}.

    :param view_name: The view name to resolve
    :type view_name: str
    :param request: The incoming request
    :type request: Request
    :param placeholder_parameters: All parameters to include with placeholders
    :type placeholder_parameters: tuple
    :param kwargs: Extra arguments, only accepting assigned_parameters
    :type kwargs: dict
    :return: The templated URI
    :rtype: str
    """
    def get_reverse_template_and_parameters(view_name):
        reverse_dict = urlresolvers.get_resolver().reverse_dict

        try:
            reverse_url_data = reverse_dict[view_name]

            reverse_url_template = reverse_url_data[0][0][0]
            reverse_url_parameters = set(reverse_url_data[0][0][1])

            return reverse_url_template, reverse_url_parameters
        except KeyError:
            raise NoReverseMatch(
                'No reverse found for "{0}"'.format(view_name)
            )

    assigned_parameters = kwargs.pop('assigned_parameters', {})
    provided_parameters = set(
        placeholder_parameters + tuple(assigned_parameters.keys())
    )

    template, url_parameters = get_reverse_template_and_parameters(view_name)

    if url_parameters == provided_parameters:
        substitutes = {
            arg: "{{{{{0}}}}}".format(arg)
            for arg in placeholder_parameters
            }

        substitutes.update(**assigned_parameters)

        return urllib.unquote(
            request.build_absolute_uri('/'+template % substitutes)
        )

    raise NoReverseMatch(
        'No reverse found for "{0}" using arguments ({1}).'.format(
            view_name,
            ', '.join(provided_parameters)
        ))
