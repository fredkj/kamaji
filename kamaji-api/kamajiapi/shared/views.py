# -*- coding: utf-8 -*-
from functools import wraps

from django.http import JsonResponse
from django.views.generic import RedirectView
from rest_framework import status
from rest_framework.generics import RetrieveDestroyAPIView
from rest_framework.response import Response
from rest_framework.views import APIView

from user_management.serializers import ActionSerializer


class RetrievePatchDestroyAPIView(RetrieveDestroyAPIView):
    """
    Implements a view that only allows PATCH as a way of updating values.
    PUT is disallowed.
    """
    def patch(self, request, *args, **kwargs):
        """
        Partially updates (Http PATCH) and no full replacement (Http PUT).
        :param request: The HttpRequest object for this update request.
        :param args: Miscellaneous args.
        :param kwargs: Miscellaneous kwargs.
        :return: A Response object containing the result of the update.
        """
        instance = self.get_object()
        serializer = self.get_serializer(
            instance, data=request.data, partial=True,
            context={'request': request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return JsonResponse(serializer.data)


class ReducedKwargsRedirectView(RedirectView):
    """
    This view will redirect the user to another specified view. Compared to
    RedirectView this view takes a list of kwargs to use when resolving the
    url, useful when you have more kwargs than you need for the redirect..
    """
    use_kwargs = None

    def get_redirect_url(self, *args, **kwargs):
        """
        Return the URL to redirect to. Uses only the kwargs specified in the
        self.use_kwargs list.

        This method will remove any items in the kwargs dict not in the
        use_kwargs list. After the a new dict is generated the method will hand
        over control to the overridden method of the super class.

        :param args: args to use in the url mapping
        :type args: list
        :param kwargs: kwargs to use in the url mapping
        :type kwargs: dict
        :return: The URL to redirect to
        :rtype: basestring
        """
        reduced_kwargs = {key: kwargs[key] for key in self.use_kwargs}

        return super(ReducedKwargsRedirectView, self).get_redirect_url(
            *args,
            **reduced_kwargs
        )


class ActionView(APIView):
    """
    The ActionView facilitates views that implementents action-subendpoints.
    To implement a child to the ActionView inherit this class and implement
    methods for any actions you would like to support.
    """

    def get_serializer(self, **kwargs):
        actions = []

        for method_name in dir(self):
            method = getattr(self, method_name)

            if hasattr(method, 'is_action'):
                actions.append(method_name)

        return ActionSerializer(actions=actions, **kwargs)

    @staticmethod
    def __generate_400_response(message=None, **field_errors):
        data = field_errors

        if message is not None:
           data['non_field_errors'] = message

        return Response(
            status=status.HTTP_400_BAD_REQUEST,
            data=data
        )

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        action = serializer.validated_data['action']

        action_method = getattr(self, action, None)

        try:
            data = request.data
            data.pop('action')
            result = action_method(**data)
        except TypeError:
            return ActionView.__generate_400_response(
                'missing required parameters'
            )

        return Response(data=result)

    @staticmethod
    def action(view_func):
        """
        Decorator for marking a method as an action that can be called
        by the ActionView it belongs to.
        """
        def _decorator(request, *args, **kwargs):
            return view_func(request, *args, **kwargs)
        wrapper = wraps(view_func)(_decorator)
        wrapper.is_action = True
        return wrapper


class LookupMixin(object):
    """
    A mixin that implements the get_object method on the view. To use add a
    queryset field to the inheriting view or override the get_queryset method.
    """
    queryset = None

    @classmethod
    def get_queryset(cls):
        assert cls.queryset is not None, \
            'Missing queryset for view "{0}".'.format(cls.__name__)

        return cls.queryset

    def get_object(self):
        return self.get_queryset().get(**self.kwargs)
