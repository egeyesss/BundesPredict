from django.urls import URLPattern, URLResolver, path

from .views import AdminMetricsView, DemoStartView

urlpatterns: list[URLPattern | URLResolver] = [
    path("admin/metrics", AdminMetricsView.as_view(), name="admin-metrics"),
    path("demo/start", DemoStartView.as_view(), name="demo-start"),
]
