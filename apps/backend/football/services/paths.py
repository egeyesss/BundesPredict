"""Where the jobs keep their downloaded files."""

from __future__ import annotations

import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]


def data_dir() -> Path:
    """The directory holding `raw/`, `tm_cache/` and `understat_cache/`.

    `BUNDESPREDICT_DATA_DIR` overrides the default `<repo>/data`, for hosts where the code
    directory is read-only.
    """
    override = os.environ.get("BUNDESPREDICT_DATA_DIR")
    return Path(override) if override else REPO_ROOT / "data"
