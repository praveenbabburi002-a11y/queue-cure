import os

from django.core.asgi import get_asgi_application

from channels.routing import (
    ProtocolTypeRouter,
    URLRouter
)

from channels.auth import (
    AuthMiddlewareStack
)

from .routing import urlpatterns


os.environ.setdefault(
    'DJANGO_SETTINGS_MODULE',
    'queue_cure.settings'
)

django_asgi_app = (
    get_asgi_application()
)

application = ProtocolTypeRouter({

    "http":
    django_asgi_app,

    "websocket":

    AuthMiddlewareStack(

        URLRouter(
            urlpatterns
        )
    ),
})