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
from django.conf.urls import include, url

from rest_framework_nested import routers

from journal import views

router = routers.DefaultRouter()
router.register(r'journals', views.JournalViewSet)
router.register(r'journal/(?P<journal_uid>[^/]+)', views.EntryViewSet)
router.register(r'user', views.UserInfoViewSet)

journals_router = routers.NestedSimpleRouter(router, r'journals', lookup='journal')
journals_router.register(r'members', views.MembersViewSet, base_name='journal-members')
journals_router.register(r'entries', views.EntryViewSet, base_name='journal-entries')


urlpatterns = [
    url(r'^api/v1/', include(router.urls)),
    url(r'^api/v1/', include(journals_router.urls)),
]

# Adding this just for testing, this shouldn't be here normally
urlpatterns += url(r'^reset/$', views.reset, name='reset_debug'),
