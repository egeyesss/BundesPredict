from django.urls import URLPattern, URLResolver, path

from .views import ConversationDetailView, ConversationListView

urlpatterns: list[URLPattern | URLResolver] = [
    path("conversations", ConversationListView.as_view(), name="conversations-list"),
    path("conversations/<uuid:id>", ConversationDetailView.as_view(), name="conversations-detail"),
]
