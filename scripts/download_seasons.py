#!/usr/bin/env python3
"""Download Bundesliga (D1) season CSVs from football-data.co.uk into data/raw/.

Just grabs the raw files — no parsing or DB work here. Idempotent: an existing
file is skipped unless --force is passed.

football-data.co.uk lays out one CSV per season at:
    https://www.football-data.co.uk/mmz4281/<SEASON>/D1.csv
where <SEASON> encodes the start/end year, e.g. 2023/24 -> "2324".

Examples:
    python scripts/download_seasons.py --start 2019 --end 2023
    python scripts/download_seasons.py --seasons 2324 2223
"""

from __future__ import annotations

import argparse
import sys
import urllib.error
import urllib.request
from pathlib import Path

BASE_URL = "https://www.football-data.co.uk/mmz4281"
DIVISION = "D1"  # Bundesliga
DEFAULT_DEST = Path(__file__).resolve().parent.parent / "data" / "raw"
USER_AGENT = "BundesPredict/0.0 (+https://github.com; educational use)"


def season_code(start_year: int) -> str:
    """2023 -> '2324' (the season starting in 2023)."""
    return f"{start_year % 100:02d}{(start_year + 1) % 100:02d}"


def download_one(code: str, dest_dir: Path, *, force: bool) -> bool:
    """Download D1.csv for one season code. Returns True if a file was written."""
    out_path = dest_dir / f"D1_{code}.csv"
    if out_path.exists() and not force:
        print(f"  skip   {out_path.name} (exists; use --force to overwrite)")
        return False

    url = f"{BASE_URL}/{code}/{DIVISION}.csv"
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310 (trusted host)
            data = resp.read()
    except urllib.error.HTTPError as exc:
        print(f"  FAIL   {code}: HTTP {exc.code} ({url})", file=sys.stderr)
        return False
    except urllib.error.URLError as exc:
        print(f"  FAIL   {code}: {exc.reason} ({url})", file=sys.stderr)
        return False

    dest_dir.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(data)
    print(f"  ok     {out_path.name} ({len(data):,} bytes)")
    return True


def resolve_codes(args: argparse.Namespace) -> list[str]:
    if args.seasons:
        return list(args.seasons)
    if args.start is not None and args.end is not None:
        if args.start > args.end:
            raise SystemExit("--start must be <= --end")
        return [season_code(y) for y in range(args.start, args.end + 1)]
    raise SystemExit("Provide either --seasons or both --start and --end.")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start", type=int, help="First season start year, e.g. 2019")
    parser.add_argument("--end", type=int, help="Last season start year, e.g. 2023")
    parser.add_argument(
        "--seasons",
        nargs="+",
        help="Explicit season codes, e.g. 2324 2223",
    )
    parser.add_argument("--dest", type=Path, default=DEFAULT_DEST, help="Output dir")
    parser.add_argument("--force", action="store_true", help="Overwrite existing files")
    args = parser.parse_args()

    codes = resolve_codes(args)
    print(f"Downloading {len(codes)} season(s) into {args.dest}")
    written = sum(download_one(c, args.dest, force=args.force) for c in codes)
    print(f"Done. {written} file(s) written, {len(codes) - written} skipped/failed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
