"""football-data.co.uk download: URL shape and error mapping, no live HTTP."""

from __future__ import annotations

import io
import urllib.error
import urllib.request
from typing import Any

import pytest

from bundespredict.data.footballdata import DownloadError, fetch_season_csv, season_url


class _Response(io.BytesIO):
    def __enter__(self) -> _Response:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()


def test_season_url_follows_the_two_digit_season_code() -> None:
    assert season_url("2324") == "https://www.football-data.co.uk/mmz4281/2324/D1.csv"


def test_fetch_returns_the_response_bytes_untouched(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[urllib.request.Request] = []

    def recorded(request: urllib.request.Request, timeout: float) -> _Response:
        seen.append(request)
        return _Response(b"Div,Date\r\nD1,18/08/2023\r\n")

    monkeypatch.setattr(urllib.request, "urlopen", recorded)

    assert fetch_season_csv("2324") == b"Div,Date\r\nD1,18/08/2023\r\n"
    assert seen[0].full_url.endswith("/2324/D1.csv")
    assert seen[0].get_header("User-agent")


def test_http_errors_become_download_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    def forbidden(request: urllib.request.Request, timeout: float) -> Any:
        raise urllib.error.HTTPError(request.full_url, 403, "Forbidden", {}, None)  # type: ignore[arg-type]

    monkeypatch.setattr(urllib.request, "urlopen", forbidden)

    with pytest.raises(DownloadError, match="2324: HTTP 403"):
        fetch_season_csv("2324")


def test_network_errors_become_download_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    def offline(request: urllib.request.Request, timeout: float) -> Any:
        raise urllib.error.URLError("name resolution failed")

    monkeypatch.setattr(urllib.request, "urlopen", offline)

    with pytest.raises(DownloadError, match="name resolution failed"):
        fetch_season_csv("2324")
