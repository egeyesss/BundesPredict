from django.urls import URLPattern, URLResolver, path

from .views import TrackRecordView

urlpatterns: list[URLPattern | URLResolver] = [
    path("track-record", TrackRecordView.as_view(), name="track-record"),
]
