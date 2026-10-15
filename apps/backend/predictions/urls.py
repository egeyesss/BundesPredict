from django.urls import URLPattern, URLResolver, path

from .views import PredictStreamView

urlpatterns: list[URLPattern | URLResolver] = [
    path("stream", PredictStreamView.as_view(), name="predict-stream"),
]
