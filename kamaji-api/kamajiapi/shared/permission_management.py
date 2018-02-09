# -*- coding: utf-8 -*-

"""
This submodule contains helper functions for creating new permissions.
"""


def create_permission(view_name):
    return {
        'view_name': view_name,
        'create': True
    }


def create_read_permission(view_name):
    return {
        'view_name': view_name,
        'create': True,
        'read': True
    }


def create_read_update_delete_permission(view_name):
    return {
        'view_name': view_name,
        'create': True,
        'read': True,
        'update': True,
        'delete': True
    }


def read_update_permission(view_name):
    return {
        'view_name': view_name,
        'read': True,
        'update': True
    }


def read_permission(view_name):
    return {
        'view_name': view_name,
        'read': True
    }


def read_delete_permission(view_name):
    return {
        'view_name': view_name,
        'read': True,
        'delete': True
    }


def read_update_delete_permission(view_name):
    return {
        'view_name': view_name,
        'read': True,
        'update': True,
        'delete': True
    }


def update_delete_permission(view_name):
    return {
        'view_name': view_name,
        'update': True,
        'delete': True
    }
