from __future__ import annotations

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.contrib.auth.models import User
from django.db.models import Model
from django.http import HttpRequest

from football.admin import ReadOnlyAdmin

from .models import UserProfile


class UserProfileInline(admin.StackedInline):  # type: ignore[type-arg]
    model = UserProfile
    can_delete = False
    readonly_fields = ("role", "is_demo", "demo_expires_at", "email_opt_in", "timezone")
    fields = readonly_fields

    def has_add_permission(self, request: HttpRequest, obj: Model | None = None) -> bool:
        return False


admin.site.unregister(User)


@admin.register(User)
class UserAdmin(DjangoUserAdmin):  # type: ignore[type-arg]
    """Sign-in is by email code or Google, so there are no passwords to manage here."""

    inlines = [UserProfileInline]
    list_display = ("email", "username", "date_joined", "last_login", "is_staff", "is_active")
    list_filter = ("is_staff", "is_superuser", "is_active", "profile__is_demo")
    search_fields = ("email", "username")
    ordering = ("-date_joined",)
    date_hierarchy = "date_joined"

    def has_add_permission(self, request: HttpRequest) -> bool:
        return False

    def has_change_permission(self, request: HttpRequest, obj: Model | None = None) -> bool:
        return request.user.is_superuser

    def has_delete_permission(self, request: HttpRequest, obj: Model | None = None) -> bool:
        return False


@admin.register(UserProfile)
class UserProfileAdmin(ReadOnlyAdmin):
    list_display = ("user", "role", "is_demo", "email_opt_in", "timezone")
    list_filter = ("role", "is_demo", "email_opt_in")
    search_fields = ("user__email", "user__username")
    list_select_related = ("user",)
