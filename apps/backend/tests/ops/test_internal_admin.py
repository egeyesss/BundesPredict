"""The Django admin pages for users, billing, chat and predictions: they render and cannot edit."""

from __future__ import annotations

import pytest
from django.contrib import admin
from django.contrib.auth.models import User
from django.db.models import Model
from django.test import Client, RequestFactory
from django.urls import reverse

from accounts.models import UserProfile
from billing.models import StripeCustomer, StripeEvent, Subscription
from chat.models import Conversation, Message
from ops.models import WebhookFailure
from predictions.models import Prediction

pytestmark = pytest.mark.django_db

READ_ONLY = [
    Subscription,
    StripeCustomer,
    StripeEvent,
    WebhookFailure,
    Conversation,
    Message,
    Prediction,
]


def url(model: type[Model], page: str = "changelist") -> str:
    return reverse(f"admin:{model._meta.app_label}_{model._meta.model_name}_{page}")


@pytest.mark.parametrize("model", [User, UserProfile, *READ_ONLY])
def test_changelist_renders_with_a_search_and_every_filter(
    admin_client: Client, model: type[Model]
) -> None:
    model_admin = admin.site._registry[model]

    assert admin_client.get(url(model)).status_code == 200
    assert admin_client.get(url(model), {"q": "x"}).status_code == 200
    for field in (f for f in model_admin.list_filter if isinstance(f, str)):
        assert admin_client.get(url(model), {field: "1"}).status_code in (200, 302)


@pytest.mark.parametrize("model", READ_ONLY)
def test_billing_chat_and_prediction_tables_are_view_only(model: type[Model]) -> None:
    request = RequestFactory().get("/admin/")
    request.user = User(is_superuser=True, is_staff=True, is_active=True)
    model_admin = admin.site._registry[model]

    assert not model_admin.has_add_permission(request)
    assert not model_admin.has_change_permission(request)
    assert not model_admin.has_delete_permission(request)


def test_only_superusers_can_edit_users() -> None:
    model_admin = admin.site._registry[User]
    staff, root = RequestFactory().get("/"), RequestFactory().get("/")
    staff.user = User(is_staff=True, is_active=True)
    root.user = User(is_staff=True, is_superuser=True, is_active=True)

    assert not model_admin.has_change_permission(staff)
    assert model_admin.has_change_permission(root)
    assert not model_admin.has_delete_permission(root)


def test_the_user_page_shows_profile_and_subscription_details(admin_client: Client) -> None:
    user = User.objects.create_user(username="reader", email="reader@example.com")

    page = admin_client.get(reverse("admin:auth_user_change", args=[user.pk]))

    assert page.status_code == 200
    assert b"is_demo" in page.content


def test_a_conversation_page_lists_its_messages(admin_client: Client) -> None:
    user = User.objects.create_user(username="chatter", email="chatter@example.com")
    conversation = Conversation.objects.create(user=user, title="Kane")
    Message.objects.create(conversation=conversation, role="user", content="Is Kane fit?")

    page = admin_client.get(reverse("admin:chat_conversation_change", args=[conversation.pk]))

    assert b"Is Kane fit?" in page.content
