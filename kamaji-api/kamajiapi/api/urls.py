# -*- coding: utf-8 -*-
from django.conf import settings
from django.conf.urls import include, url
from django.contrib import admin
from django.views import static

from rest_framework_jwt.views import refresh_jwt_token, obtain_jwt_token

from api.views import (
    APIRootLinksList, StatusView, AuthLinksList
)

urlpatterns = [
    url(r'^statics/(?P<path>.*)$',
        static.serve, {'document_root': settings.MEDIA_ROOT}
    ),
    url(r'^$', APIRootLinksList.as_view(), name='api-root'),
    url(r'^status/', StatusView.as_view(), name='status'),
    url(r'^admin/', include(admin.site.urls)),
    url(r'^api-auth/',
        include('rest_framework.urls', namespace='rest_framework')
    ),
    url(r'^auth/$', AuthLinksList.as_view(), name='auth-root'),
    url(r'^auth/token/$', obtain_jwt_token, name='token'),
    url(r'^auth/token/refresh/', refresh_jwt_token, name='token-refresh'),
    url(r'^', include('fabric.urls'), name='fabric'),
    url(r'^', include('user_management.urls'), name='user_management'),
]
