"""Game version tracking: fetch, cache, and query game update dates."""
from __future__ import annotations

import json
import os
from datetime import date, timedelta
from typing import Optional

import httpx

from . import logger, paths
from .remote_cache import RemoteCache


def _on_game_versions_http_error(exc: httpx.HTTPStatusError) -> None:
    code = exc.response.status_code
    if code == 404:
        logger.log(
            "info",
            "No game_versions.json on remote (not published yet), "
            "using bundled or empty fallback",
        )
    else:
        logger.log(
            "warning",
            f"Failed to fetch game versions (HTTP {code}): {exc.response.reason_phrase}",
        )


_game_versions_cache = RemoteCache(
    url="https://raw.githubusercontent.com/PetricaT/IsaacMM/main/game_versions.json",
    cache_path=os.path.join(paths.appdata, "game_versions.json"),
    bundled_path=os.path.join(paths.BASE_DIR, "game_versions.json"),
    ttl=timedelta(days=30),
    parse_fn=lambda raw: json.loads(raw),
    fallback={},
    on_http_error=_on_game_versions_http_error,
)


def fetch_background() -> Optional[bool]:
    return _game_versions_cache.fetch_background()


def get_game_versions() -> dict[str, str]:
    return _game_versions_cache.get()


def fetch_initial() -> None:
    get_game_versions()


def get_latest_update_date() -> Optional[date]:
    versions = get_game_versions()
    if not versions:
        return None
    latest: Optional[date] = None
    for version_str, date_str in versions.items():
        try:
            parsed = date.fromisoformat(date_str)
        except (ValueError, TypeError):
            continue
        if latest is None or parsed > latest:
            latest = parsed
    return latest


def _parse_major_minor(version_str: str) -> Optional[tuple[int, int]]:
    parts = version_str.split(".")
    try:
        major = int(parts[0])
        minor = int(parts[1]) if len(parts) > 1 else 0
        return (major, minor)
    except (ValueError, IndexError):
        return None


def get_outdated_thresholds() -> tuple[Optional[date], Optional[date]]:
    """
    Returns (latest_update_date, previous_major_date):
    - latest_update_date: date of the latest game version
    - previous_major_date: date of the latest update in the
      previous major.minor era. Returns None if only one major.minor
      group exists (no two-major-version-ago baseline).
    """
    versions = get_game_versions()
    if not versions:
        return (None, None)

    era_dates: dict[tuple[int, int], date] = {}
    for version_str, date_str in versions.items():
        mm = _parse_major_minor(version_str)
        if mm is None:
            continue
        try:
            parsed = date.fromisoformat(date_str)
        except (ValueError, TypeError):
            continue
        if mm not in era_dates or parsed > era_dates[mm]:
            era_dates[mm] = parsed

    if not era_dates:
        return (None, None)

    sorted_eras = sorted(era_dates.keys(), reverse=True)
    latest = era_dates[sorted_eras[0]]
    previous = era_dates[sorted_eras[1]] if len(sorted_eras) > 1 else None
    return (latest, previous)



