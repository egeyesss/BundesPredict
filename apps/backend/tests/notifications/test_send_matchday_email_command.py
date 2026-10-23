"""`send_matchday_email` mails opted-in Pro users once per matchday and never twice."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from io import StringIO
from typing import Any

import pytest
from anymail.exceptions import AnymailAPIError
from django.contrib.auth.models import User
from django.core import mail
from django.core.mail import EmailMultiAlternatives
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import IntegrityError, transaction

from billing.models import StripeCustomer, Subscription
from football.models import Fixture, Match, ModelRun, Team, TeamParam
from notifications.models import EmailSend
from notifications.tokens import user_id_from_token
from track_record.models import FixturePrediction

pytestmark = pytest.mark.django_db

THURSDAY = datetime(2026, 10, 15, 12, 0, tzinfo=UTC)
STRENGTHS = {"FCB": (0.5, -0.4), "RBL": (0.1, -0.1), "BVB": (0.3, -0.2), "S04": (-0.3, 0.3)}
CAMPAIGN = "matchday-2627-06"


@pytest.fixture(autouse=True)
def no_live_keys(settings: Any) -> None:
    settings.STRIPE_SECRET_KEY_LIVE = ""


@pytest.fixture
def league() -> dict[str, Team]:
    teams = {
        code: Team.objects.create(name=name, code=code, short_name=name)
        for code, name in [
            ("FCB", "Bayern"),
            ("RBL", "Leipzig"),
            ("BVB", "Dortmund"),
            ("S04", "Schalke"),
        ]
    }
    run = ModelRun.objects.create(
        model_type="dixon_coles",
        version="serve",
        xi=0.0018,
        rho=-0.1,
        home_adv=0.25,
        log_likelihood=-1000.0,
        n_matches=5000,
        trained_at=THURSDAY - timedelta(days=1),
    )
    for code, team in teams.items():
        TeamParam.objects.create(
            model_run=run, team=team, attack=STRENGTHS[code][0], defense=STRENGTHS[code][1]
        )
    return teams


@pytest.fixture
def matchday(league: dict[str, Team]) -> list[Fixture]:
    return [
        Fixture.objects.create(
            season="2627",
            matchday=6,
            kickoff_utc=THURSDAY + timedelta(days=2, hours=1, minutes=30),
            home=league["FCB"],
            away=league["RBL"],
        ),
        Fixture.objects.create(
            season="2627",
            matchday=6,
            kickoff_utc=THURSDAY + timedelta(days=3, hours=1, minutes=30),
            home=league["BVB"],
            away=league["S04"],
        ),
    ]


MakeUser = Callable[..., User]


@pytest.fixture
def make_user() -> MakeUser:
    def build(
        email: str,
        *,
        pro: bool = True,
        opted_in: bool = True,
        timezone: str | None = "America/Toronto",
        demo: bool = False,
        active: bool = True,
        first_name: str = "",
    ) -> User:
        user = User.objects.create_user(
            username=email, email=email, first_name=first_name, is_active=active
        )
        user.profile.email_opt_in = opted_in
        user.profile.timezone = timezone
        user.profile.is_demo = demo
        user.profile.save()
        if pro:
            customer = StripeCustomer.objects.create(
                user=user, livemode=False, customer_id=f"cus_{user.pk}"
            )
            Subscription.objects.create(
                customer=customer,
                subscription_id=f"sub_{user.pk}",
                livemode=False,
                status="active",
                current_period_end=THURSDAY + timedelta(days=20),
            )
        return user

    return build


def send(**options: Any) -> str:
    out = StringIO()
    call_command("send_matchday_email", now=THURSDAY.isoformat(), delay=0, stdout=out, **options)
    return out.getvalue()


def recipients() -> list[str]:
    return sorted(address for message in mail.outbox for address in message.to)


def test_sends_only_to_opted_in_pro_users(matchday: list[Fixture], make_user: MakeUser) -> None:
    make_user("pro@example.com")
    make_user("free@example.com", pro=False)
    make_user("optedout@example.com", opted_in=False)
    make_user("demo@example.com", demo=True)
    make_user("inactive@example.com", active=False)
    User.objects.filter(pk=make_user("blank@example.com").pk).update(email="")

    send()

    assert recipients() == ["pro@example.com"]
    assert list(EmailSend.objects.values_list("user__email", "campaign")) == [
        ("pro@example.com", CAMPAIGN)
    ]


def test_running_again_sends_nothing(matchday: list[Fixture], make_user: MakeUser) -> None:
    make_user("one@example.com")
    make_user("two@example.com")

    send()
    assert len(mail.outbox) == 2
    second = send()

    assert len(mail.outbox) == 2
    assert EmailSend.objects.count() == 2
    assert "sent 0" in second


def test_a_user_who_joins_pro_between_runs_gets_the_mail_once(
    matchday: list[Fixture], make_user: MakeUser
) -> None:
    make_user("early@example.com")
    send()
    make_user("late@example.com")

    send()

    assert recipients() == ["early@example.com", "late@example.com"]


def test_the_database_refuses_a_second_row_for_the_same_user_and_campaign(
    make_user: MakeUser,
) -> None:
    user = make_user("one@example.com")
    EmailSend.objects.create(user=user, campaign=CAMPAIGN)

    with pytest.raises(IntegrityError), transaction.atomic():
        EmailSend.objects.create(user=user, campaign=CAMPAIGN)


def test_the_next_matchday_is_a_new_campaign(
    matchday: list[Fixture], league: dict[str, Team], make_user: MakeUser
) -> None:
    make_user("one@example.com")
    send()
    Fixture.objects.create(
        season="2627",
        matchday=7,
        kickoff_utc=THURSDAY + timedelta(days=9),
        home=league["RBL"],
        away=league["BVB"],
    )
    Fixture.objects.filter(matchday=6).update(kickoff_utc=THURSDAY - timedelta(days=1))

    call_command(
        "send_matchday_email",
        now=(THURSDAY + timedelta(days=7)).isoformat(),
        delay=0,
        stdout=StringIO(),
    )

    assert sorted(EmailSend.objects.values_list("campaign", flat=True)) == [
        CAMPAIGN,
        "matchday-2627-07",
    ]
    assert len(mail.outbox) == 2


def test_every_message_is_individual_and_carries_the_unsubscribe_headers(
    matchday: list[Fixture], make_user: MakeUser
) -> None:
    pro = make_user("pro@example.com")
    make_user("other@example.com")

    send()

    message = next(m for m in mail.outbox if m.to == ["pro@example.com"])
    assert message.from_email == "BundesPredict <bundespredict@egeyesilyurt.ca>"
    assert message.reply_to == ["bundespredict@egeyesilyurt.ca"]
    url = message.extra_headers["List-Unsubscribe"]
    assert url.startswith("<https://bundespredict.egeyesilyurt.ca/api/v1/email/unsubscribe?token=")
    assert url.endswith(">")
    assert message.extra_headers["List-Unsubscribe-Post"] == "List-Unsubscribe=One-Click"
    assert user_id_from_token(url.split("token=")[1].rstrip(">")) == pro.pk


def test_the_message_has_a_text_alternative_with_the_same_content(
    matchday: list[Fixture], make_user: MakeUser
) -> None:
    make_user("pro@example.com")

    send()

    message = mail.outbox[0]
    assert message.subject.startswith("Matchday 6: ")
    assert isinstance(message, EmailMultiAlternatives)
    html = str(message.alternatives[0][0])
    for name in ("Bayern", "Leipzig", "Dortmund", "Schalke"):
        assert name in message.body
        assert name in html
    assert "https://bundespredict.egeyesilyurt.ca/email/unsubscribe?t=" in message.body
    assert "L4B 0J4, Canada" in message.body


def test_uses_the_frozen_prediction_when_there_is_one(
    matchday: list[Fixture], make_user: MakeUser
) -> None:
    make_user("pro@example.com")
    fixture = matchday[0]
    FixturePrediction.objects.create(
        fixture=fixture,
        model_run=ModelRun.objects.get(),
        p_home=0.7,
        p_draw=0.2,
        p_away=0.1,
        exp_home_goals=2.5,
        exp_away_goals=0.9,
        score_grid=[[0.0] * 11 for _ in range(11)],
        created_at=THURSDAY - timedelta(hours=1),
    )

    send()

    assert "70%" in mail.outbox[0].body
    assert "xG 2.50 – 0.90" in mail.outbox[0].body


def test_a_failed_send_is_retried_by_the_next_run(
    matchday: list[Fixture], make_user: MakeUser, monkeypatch: pytest.MonkeyPatch
) -> None:
    make_user("pro@example.com")
    real_send = EmailMultiAlternatives.send

    def failing(self: EmailMultiAlternatives, *args: Any, **kwargs: Any) -> int:
        raise AnymailAPIError("resend is down")

    monkeypatch.setattr(EmailMultiAlternatives, "send", failing)
    with pytest.raises(CommandError, match="1 of 1"):
        send()
    assert EmailSend.objects.count() == 0

    monkeypatch.setattr(EmailMultiAlternatives, "send", real_send)
    send()

    assert recipients() == ["pro@example.com"]
    assert EmailSend.objects.count() == 1


def test_nothing_is_sent_when_the_next_matchday_is_far_away(
    matchday: list[Fixture], make_user: MakeUser
) -> None:
    make_user("pro@example.com")
    Fixture.objects.update(kickoff_utc=THURSDAY + timedelta(days=21))

    output = send()

    assert mail.outbox == []
    assert "no matchday" in output


def test_recipient_option_sends_one_test_mail_and_records_nothing(
    matchday: list[Fixture], make_user: MakeUser
) -> None:
    make_user("pro@example.com")
    make_user("other@example.com")

    send(recipient="pro@example.com")
    send(recipient="pro@example.com")

    assert recipients() == ["pro@example.com", "pro@example.com"]
    assert EmailSend.objects.count() == 0


def test_the_footer_address_comes_from_a_setting(
    matchday: list[Fixture], make_user: MakeUser, settings: Any
) -> None:
    settings.MAILING_ADDRESS = "1 Test Street, Toronto"
    make_user("pro@example.com")

    send()

    assert "1 Test Street, Toronto" in mail.outbox[0].body


def test_reports_how_the_last_matchday_went(
    matchday: list[Fixture], league: dict[str, Team], make_user: MakeUser
) -> None:
    make_user("pro@example.com")
    played = Fixture.objects.create(
        season="2627",
        matchday=5,
        kickoff_utc=THURSDAY - timedelta(days=5),
        home=league["FCB"],
        away=league["BVB"],
    )
    FixturePrediction.objects.create(
        fixture=played,
        model_run=ModelRun.objects.get(),
        p_home=0.6,
        p_draw=0.25,
        p_away=0.15,
        exp_home_goals=2.0,
        exp_away_goals=1.0,
        score_grid=[[0.0] * 11 for _ in range(11)],
        created_at=THURSDAY - timedelta(days=6),
    )
    Match.objects.create(
        season="2627",
        date=played.kickoff_utc.date(),
        home=league["FCB"],
        away=league["BVB"],
        home_goals=2,
        away_goals=0,
        ftr="H",
    )

    send()

    assert "The favourite won 1 of 1" in mail.outbox[0].body
    assert "Model RPS 0.091" in mail.outbox[0].body
