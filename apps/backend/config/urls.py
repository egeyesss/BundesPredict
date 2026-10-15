from django.contrib import admin
from django.urls import include, path

from .views import HealthView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/health", HealthView.as_view(), name="health"),
    path("api/v1/", include("football.urls")),
    path("api/v1/predict/", include("predictions.urls")),
    path("api/v1/", include("accounts.urls")),
    path("api/v1/", include("chat.urls")),
    path("api/v1/billing/", include("billing.urls")),
    path("api/v1/", include("track_record.urls")),
    path("api/v1/email/", include("notifications.urls")),
    path("api/v1/", include("ops.urls")),
    # Outside /api/v1: the allauth headless and OAuth callback routes, and Stripe's webhooks.
    path("", include("accounts.auth_urls")),
    path("stripe/webhook/", include("billing.webhook_urls")),
]
