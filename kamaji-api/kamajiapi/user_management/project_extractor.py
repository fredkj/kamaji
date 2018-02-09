# -*- coding: utf-8 -*-
from abc import abstractmethod, ABCMeta


class ProjectExtractor(object):
    """
    Abstract Base Class for providing a custom project extraction method during
    the permission assessment.
    A custom project extraction method needs to be provided when a call to a
    View is connected to a specific project but it is not obvious which project
    from directly looking in the data attribute or kwargs of the request.
    """
    __metaclass__ = ABCMeta

    @abstractmethod
    def extract_project(self, request):
        """
        Extract the project from the request and return the Project model
        instance.

        :note: Override this method if the designated project cannot be \
        easily extracted from the request by the common implemented solutions.
        :param request: The incoming request.
        :type request: HttpRequest
        :return: The model instance of the request.
        :rtype: Project
        """
        pass
