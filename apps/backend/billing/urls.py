from django.urls import URLPattern, URLResolver, path

from .views import CheckoutView, PortalView

urlpatterns: list[URLPattern | URLResolver] = [
    path("checkout", CheckoutView.as_view(), name="billing-checkout"),
    path("portal", PortalView.as_view(), name="billing-portal"),
]
