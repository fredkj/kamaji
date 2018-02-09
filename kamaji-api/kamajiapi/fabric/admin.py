# -*- coding: utf-8 -*-
from django.contrib import admin
from fabric.models import Node, PhysicalNetwork

admin.site.register(PhysicalNetwork)


class NodeAdmin(admin.ModelAdmin):
    pass


# Register your models here.
admin.site.register(Node, NodeAdmin)
