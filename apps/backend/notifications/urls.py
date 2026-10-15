from django.urls import URLPattern, URLResolver, path

from .views import UnsubscribeView

urlpatterns: list[URLPattern | URLResolver] = [
    path("unsubscribe", UnsubscribeView.as_view(), name="email-unsubscribe"),
]
