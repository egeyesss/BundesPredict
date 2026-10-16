"""Conversation titles come from the first query."""

from __future__ import annotations

from chat.models import TITLE_MAX_LENGTH, Conversation


def test_a_short_query_is_the_title() -> None:
    assert Conversation.title_for("Bayern v Dortmund") == "Bayern v Dortmund"


def test_a_long_query_is_cut_to_sixty_characters() -> None:
    title = Conversation.title_for("x" * 200)

    assert TITLE_MAX_LENGTH == 60
    assert title == "x" * 60


def test_surrounding_whitespace_is_trimmed_before_cutting() -> None:
    assert Conversation.title_for("   Kane is out  \n") == "Kane is out"
