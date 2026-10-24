"""The unsubscribe token is signed and single-purpose; the endpoint flips the opt-in flag."""

from __future__ import annotations

import pytest
from django.contrib.auth.models import User
from django.core import signing
from rest_framework.test import APIClient

from notifications.tokens import InvalidUnsubscribeToken, unsubscribe_token, user_id_from_token

pytestmark = pytest.mark.django_db

URL = "/api/v1/email/unsubscribe"


@pytest.fixture
def user() -> User:
    reader = User.objects.create_user(username="reader", email="reader@example.com")
    reader.profile.email_opt_in = True
    reader.profile.save()
    return reader


def test_token_round_trips_to_the_user_id(user: User) -> None:
    assert user_id_from_token(unsubscribe_token(user.pk)) == user.pk


def test_a_tampered_token_is_rejected(user: User) -> None:
    token = unsubscribe_token(user.pk)

    with pytest.raises(InvalidUnsubscribeToken):
        user_id_from_token(token[:-2] + ("AA" if not token.endswith("AA") else "BB"))


def test_garbage_is_rejected() -> None:
    with pytest.raises(InvalidUnsubscribeToken):
        user_id_from_token("not-a-token")


def test_a_token_signed_for_another_purpose_is_rejected(user: User) -> None:
    other_purpose = signing.dumps({"user": user.pk}, salt="accounts.something-else")

    with pytest.raises(InvalidUnsubscribeToken):
        user_id_from_token(other_purpose)


def test_a_token_without_a_user_is_rejected() -> None:
    token = signing.dumps({"nobody": 1}, salt="notifications.unsubscribe")

    with pytest.raises(InvalidUnsubscribeToken):
        user_id_from_token(token)


def test_post_with_a_json_token_turns_the_opt_in_off(api_client: APIClient, user: User) -> None:
    assert user.profile.email_opt_in is True

    response = api_client.post(URL, {"token": unsubscribe_token(user.pk)}, format="json")

    assert response.status_code == 204
    user.profile.refresh_from_db()
    assert user.profile.email_opt_in is False


def test_one_click_post_from_a_mail_client_works(api_client: APIClient, user: User) -> None:
    """Gmail POSTs `List-Unsubscribe=One-Click` as a form to the URL from the header."""
    response = api_client.post(
        f"{URL}?token={unsubscribe_token(user.pk)}",
        {"List-Unsubscribe": "One-Click"},
        format="multipart",
    )

    assert response.status_code == 204
    user.profile.refresh_from_db()
    assert user.profile.email_opt_in is False


def test_unsubscribing_twice_is_fine(api_client: APIClient, user: User) -> None:
    token = unsubscribe_token(user.pk)

    first = api_client.post(URL, {"token": token}, format="json")
    second = api_client.post(URL, {"token": token}, format="json")

    assert (first.status_code, second.status_code) == (204, 204)


def test_a_bad_token_answers_400_and_changes_nothing(api_client: APIClient, user: User) -> None:
    response = api_client.post(URL, {"token": "nope"}, format="json")

    assert response.status_code == 400
    assert response.json()["code"] == "invalid_token"
    user.profile.refresh_from_db()
    assert user.profile.email_opt_in is True


def test_a_missing_token_answers_400(api_client: APIClient) -> None:
    response = api_client.post(URL, {}, format="json")

    assert response.status_code == 400
    assert response.json()["code"] == "validation_error"


def test_a_token_for_a_deleted_user_is_a_no_op(api_client: APIClient, user: User) -> None:
    token = unsubscribe_token(user.pk)
    user.delete()

    response = api_client.post(URL, {"token": token}, format="json")

    assert response.status_code == 204
