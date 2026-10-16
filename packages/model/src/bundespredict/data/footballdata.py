"""Download Bundesliga (D1) season CSVs from football-data.co.uk.

Network only: the bytes come back untouched so the caller decides where they are cached.
Parsing lives in :mod:`bundespredict.data.parse`.
"""

from __future__ import annotations

import urllib.error
import urllib.request

BASE_URL = "https://www.football-data.co.uk/mmz4281"
DIVISION = "D1"
USER_AGENT = "BundesPredict/0.0 (+https://github.com; educational use)"


class DownloadError(RuntimeError):
    """The season file could not be fetched (HTTP error or network failure)."""


def season_url(code: str) -> str:
    return f"{BASE_URL}/{code}/{DIVISION}.csv"


def fetch_season_csv(code: str, *, timeout: float = 30) -> bytes:
    """Download ``D1.csv`` for one season code such as ``"2324"``."""
    url = season_url(code)
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
            return bytes(response.read())
    except urllib.error.HTTPError as exc:
        raise DownloadError(f"{code}: HTTP {exc.code} ({url})") from exc
    except urllib.error.URLError as exc:
        raise DownloadError(f"{code}: {exc.reason} ({url})") from exc
