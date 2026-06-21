from django.contrib import admin
from django.urls import path
from django.urls import include

urlpatterns = [

    path(
        'admin/',
        admin.site.urls
    ),

    path(
        '',
        include('queue_app.urls')
    ),

    path(
        'accounts/',
        include('accounts.urls')
    ),

    path(
        'api/',
        include('api.urls')
    ),
]