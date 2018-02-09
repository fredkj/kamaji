# -*- coding: utf-8 -*-
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import Group, User
from django.utils.translation import ugettext_lazy as _

from user_management.models import GlobalGroup, ProjectGroup, Project


class KamajiUserAdmin(UserAdmin):
    UserAdmin.fieldsets = (
        (None, {'fields': ('username', 'password')}),
        (_('Personal info'), {'fields': ('first_name', 'last_name', 'email')}),
        (_('Important dates'), {'fields': ('last_login', 'date_joined')})
    )

# Add models to admin interface
admin.site.register(ProjectGroup)
admin.site.register(GlobalGroup)
admin.site.register(Project)

# Remove standard User and Group from admin interface
admin.site.unregister(Group)
admin.site.unregister(User)

# re-register our custom UserModelAdmin
admin.site.register(User, KamajiUserAdmin)
