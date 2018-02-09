# -*- coding: utf-8 -*-
import inspect
import logging

logger = logging.getLogger(__name__)


class Rollbacks(object):
    """
    Context Manager with rollbacks that are run whenever an exception is
    raised within its context.
    """
    def __init__(self, *rollbacks):
        """
        :param rollbacks: rollback functions to run if an error occurs within
        this context.
        """
        if len(rollbacks) == 0:
            raise AttributeError('rollbacks must be specified.')
        self.rollbacks = rollbacks

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_val is not None:
            logger.exception('Failed while executing transaction.')

            for rollback in self.rollbacks:
                try:
                    rollback()
                except:
                    # We have no facilities to handle a failed rollback so
                    # just log it
                    logger.error(
                        'Failed while executing rollback %s.',
                        self.__get_method_namespace(rollback)
                    )
            return False
        return True

    @staticmethod
    def __get_method_namespace(function):
        """Get a nice string representation of a function."""
        class_name = Rollbacks.__get_class_name(function)
        method_name = function.__name__
        return '{0}.{1}'.format(class_name, method_name)

    @staticmethod
    def __get_class_name(method):
        """Get the class name of a method, returns unbound for non-methods."""
        if hasattr(method, 'im_class'):
            for klass in inspect.getmro(method.im_class):
                if method.__name__ in klass.__dict__:
                    return klass.__name__
        return 'unbound'
