from django.urls import URLPattern, URLResolver, path

from .views import MeView

urlpatterns: list[URLPattern | URLResolver] = [
    path("me", MeView.as_view(), name="me"),
]
