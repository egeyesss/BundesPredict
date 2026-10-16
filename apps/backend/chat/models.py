"""Saved conversations: one row per chat thread and one per message in it."""

from __future__ import annotations

import uuid

from django.conf import settings
from django.db import models

TITLE_MAX_LENGTH = 60


class Conversation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="conversations"
    )
    title = models.CharField(max_length=TITLE_MAX_LENGTH)
    fixture = models.ForeignKey(
        "football.Fixture", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [models.Index(fields=["user", "-updated_at"], name="ix_conversation_user_recent")]

    def __str__(self) -> str:
        return f"conversation {self.pk}"

    @staticmethod
    def title_for(query: str) -> str:
        """The first query, trimmed, cut to what the title column holds."""
        return query.strip()[:TITLE_MAX_LENGTH].strip()


class Message(models.Model):
    class Role(models.TextChoices):
        USER = "user"
        ASSISTANT = "assistant"

    conversation = models.ForeignKey(
        Conversation, on_delete=models.CASCADE, related_name="messages"
    )
    role = models.CharField(max_length=10, choices=Role.choices)
    content = models.TextField()
    prediction = models.ForeignKey(
        "predictions.Prediction",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="messages",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["id"]

    def __str__(self) -> str:
        return f"{self.role} message {self.pk}"
