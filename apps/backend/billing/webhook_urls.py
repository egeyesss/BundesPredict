from django.urls import URLPattern, URLResolver, path

from .views import StripeLiveWebhookView, StripeTestWebhookView

urlpatterns: list[URLPattern | URLResolver] = [
    path("live", StripeLiveWebhookView.as_view(), name="stripe-webhook-live"),
    path("test", StripeTestWebhookView.as_view(), name="stripe-webhook-test"),
]
