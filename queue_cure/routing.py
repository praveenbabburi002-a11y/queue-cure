from django.urls import re_path

from queue_app.routing import (
    websocket_urlpatterns
)

urlpatterns = websocket_urlpatterns