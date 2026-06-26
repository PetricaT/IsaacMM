"""Game version tracking: fetch, cache, and query game update dates."""
import json
import os
import ssl
import threading
from datetime import date, datetime, timedelta
from typing import Optional
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from . import logger, paths

_ssl_context = ssl.create_default_context()
_game_versions_lock = threading.Lock()

GAME_VERSIONS_URL: str = (
    "https://raw.githubusercontent.com/PetricaT/IsaacMM/main/game_versions.json"
)
CACHE_FILE: str = os.path.join(paths.appdata, "game_versions.json")
CACHE_TTL: timedelta = timedelta(days=30)

_game_versions: Optional[dict[str, str]] = None


def fetch_background() -> Optional[bool]:
    global _game_versions
    with _game_versions_lock:
        if _is_cache_fresh():
            return None
        json_data = _try_fetch()
        if json_data is not None:
            _game_versions = json_data
            return True
        return False


def get_game_versions() -> dict[str, str]:
    global _game_versions
    with _game_versions_lock:
        if _game_versions is not None:
            return _game_versions

        json_data = None
        if _is_cache_fresh():
            json_data = _try_cache()

        if json_data is None:
            json_data = _try_fetch()

        if json_data is None:
            json_data = _try_cache()

        if json_data is None:
            json_data = _try_bundled()

        if json_data is None:
            json_data = {}

        _game_versions = json_data
        return _game_versions


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


def _is_cache_fresh() -> bool:
    try:
        if not os.path.exists(CACHE_FILE):
            return False
        file_mtime = datetime.fromtimestamp(os.path.getmtime(CACHE_FILE))
        return datetime.now() - file_mtime <= CACHE_TTL
    except OSError:
        return False


def _try_fetch() -> Optional[dict[str, str]]:
    try:
        request = Request(GAME_VERSIONS_URL, headers={"User-Agent": "IsaacMM/1.0"})
        with urlopen(request, timeout=10, context=_ssl_context) as response:
            raw_content = response.read().decode("utf-8")
        json_data = json.loads(raw_content)
        os.makedirs(paths.appdata, exist_ok=True)
        with open(CACHE_FILE, "w") as cache_file:
            cache_file.write(raw_content)
        return json_data
    except HTTPError as exc:
        if exc.code == 404:
            logger.log(
                "info",
                "No game_versions.json on remote (not published yet), "
                "using bundled or empty fallback",
            )
        else:
            logger.log(
                "warning",
                f"Failed to fetch game versions (HTTP {exc.code}): {exc.reason}",
            )
        return None
    except URLError:
        logger.log("warning", "No network, cannot fetch latest game versions")
        return None
    except (OSError, json.JSONDecodeError) as exc:
        logger.log("error", f"Error loading game versions: {exc}")
        return None


def _try_cache() -> Optional[dict[str, str]]:
    try:
        with open(CACHE_FILE) as cache_file:
            return json.load(cache_file)
    except (OSError, json.JSONDecodeError):
        return None


def _try_bundled() -> Optional[dict[str, str]]:
    bundled_path = os.path.join(paths.BASE_DIR, "game_versions.json")
    try:
        with open(bundled_path) as bundled_file:
            return json.load(bundled_file)
    except (OSError, json.JSONDecodeError):
        return None
