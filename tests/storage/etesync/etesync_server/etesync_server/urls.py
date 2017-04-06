"""etesync_server URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/1.10/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  url(r'^$', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  url(r'^$', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.conf.urls import url, include
    2. Add a URL to urlpatterns:  url(r'^blog/', include('blog.urls'))
"""
from django.conf import settings
from django.conf.urls import include, url
from django.contrib import admin

from rest_framework import routers
from rest_framework.authtoken import views as token_views

from journal import views

router = routers.DefaultRouter()
router.register(r'journals', views.JournalViewSet)
router.register(r'journal/(?P<journal>[^/]+)', views.EntryViewSet)

urlpatterns = [
    url(r'^api/v1/', include(router.urls)),
    url(r'^api-auth/', include('rest_framework.urls', namespace='rest_framework')),  # noqa
    url(r'^api-token-auth/', token_views.obtain_auth_token),
]

if settings.DEBUG:
    urlpatterns += url(r'^reset/$', views.reset, name='reset_debug'),

urlpatterns += url(r'^admin/', admin.site.urls),
