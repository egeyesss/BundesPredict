"""Conversation lookups shared by the chat endpoints and the predict stream."""

from __future__ import annotations

import uuid

from django.contrib.auth.models import User
from rest_framework.exceptions import NotFound

from .models import Conversation

# Bounds what a long thread adds to every later LLM call.
HISTORY_TURNS = 20


def owned_conversation(user: User, conversation_id: uuid.UUID) -> Conversation:
    """The user's own conversation; a missing one and someone else's are the same 404."""
    conversation = Conversation.objects.filter(pk=conversation_id, user=user).first()
    if conversation is None:
        raise NotFound()
    return conversation


def history_for(conversation: Conversation) -> list[dict[str, str]]:
    """The latest saved turns, oldest first, in the shape the agent loop takes as history."""
    latest = conversation.messages.order_by("-id")[:HISTORY_TURNS]
    return [{"role": m.role, "content": m.content} for m in reversed(list(latest))]
