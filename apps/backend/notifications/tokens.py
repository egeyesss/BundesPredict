"""Signed unsubscribe tokens. The salt makes a token useless for any other signed value."""

from __future__ import annotations

from django.core import signing

SALT = "notifications.unsubscribe"


class InvalidUnsubscribeToken(ValueError):
    pass


def unsubscribe_token(user_id: int) -> str:
    return signing.dumps({"user": user_id}, salt=SALT, compress=True)


def user_id_from_token(token: str) -> int:
    try:
        payload = signing.loads(token, salt=SALT)
    except signing.BadSignature as error:
        raise InvalidUnsubscribeToken("the unsubscribe token is not valid") from error
    user_id = payload.get("user") if isinstance(payload, dict) else None
    if not isinstance(user_id, int):
        raise InvalidUnsubscribeToken("the unsubscribe token does not name a user")
    return user_id
