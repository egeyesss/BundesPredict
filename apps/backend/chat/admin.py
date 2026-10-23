from __future__ import annotations

from django.contrib import admin
from django.db.models import Model
from django.http import HttpRequest

from football.admin import ReadOnlyAdmin

from .models import Conversation, Message


class MessageInline(admin.TabularInline):  # type: ignore[type-arg]
    model = Message
    extra = 0
    fields = ("role", "content", "prediction", "created_at")
    readonly_fields = fields
    can_delete = False

    def has_add_permission(self, request: HttpRequest, obj: Model | None = None) -> bool:
        return False


@admin.register(Conversation)
class ConversationAdmin(ReadOnlyAdmin):
    list_display = ("title", "user", "fixture", "created_at", "updated_at")
    list_filter = ("created_at",)
    search_fields = ("title", "user__email", "messages__content")
    list_select_related = ("user", "fixture")
    ordering = ("-updated_at",)
    inlines = [MessageInline]


@admin.register(Message)
class MessageAdmin(ReadOnlyAdmin):
    list_display = ("id", "conversation", "role", "created_at")
    list_filter = ("role",)
    search_fields = ("content", "conversation__user__email")
    list_select_related = ("conversation",)
