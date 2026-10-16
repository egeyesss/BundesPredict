from django.urls import URLPattern, URLResolver, path

from .views import FixtureDetailView, FixtureListView, TeamListView

urlpatterns: list[URLPattern | URLResolver] = [
    path("teams", TeamListView.as_view(), name="teams-list"),
    path("fixtures", FixtureListView.as_view(), name="fixtures-list"),
    path("fixtures/<int:id>", FixtureDetailView.as_view(), name="fixtures-detail"),
]
