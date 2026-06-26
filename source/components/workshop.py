"""Steam Workshop integration: download icons, rate limiting, queue, details."""
import json
import os
import re
import ssl
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import deque
from datetime import datetime
from typing import Optional, Tuple

from .. import config, logger, paths

_ssl_context = ssl._create_unverified_context()
_workshop_lock = threading.Lock()

_WORKSHOP_LIMITER: deque = deque()
WORKSHOP_RATE_LIMIT: int = 180
WORKSHOP_RATE_WINDOW: int = 300
WORKSHOP_RETRY_COOLDOWN: int = 300
_failed_workshop_ids: dict[str, float] = {}
_permanent_failures: set[str] = set()
_pending_workshop_ids: set[str] = set()
_workshop_queue: deque[tuple[str, str]] = deque()

DETAILS_CACHE_FILE: str = os.path.join(paths.cache_dir, "workshop_details.json")
_workshop_details_cache: dict[str, dict] = {}
_details_queue: deque[str] = deque()
_details_pending_ids: set[str] = set()


def _workshop_queue_length() -> int:
    with _workshop_lock:
        return len(_workshop_queue)


def _enqueue_workshop(ws_id: str, normalized_name: str) -> bool:
    with _workshop_lock:
        for wid, _ in _workshop_queue:
            if wid == ws_id:
                return False
        if ws_id in _pending_workshop_ids:
            return False
        _workshop_queue.append((ws_id, normalized_name))
        return True


def _dequeue_workshop() -> Optional[tuple[str, str]]:
    with _workshop_lock:
        return _workshop_queue.popleft() if _workshop_queue else None


def _discard_from_queue(ws_id: str) -> None:
    with _workshop_lock:
        for i, (wid, _) in enumerate(_workshop_queue):
            if wid == ws_id:
                del _workshop_queue[i]
                break


def _requeue_workshop(ws_id: str, normalized_name: str) -> None:
    with _workshop_lock:
        _workshop_queue.appendleft((ws_id, normalized_name))


def _init_workshop_limiter() -> None:
    now = time.time()
    with _workshop_lock:
        _WORKSHOP_LIMITER.clear()
        for ts in config.workshop_timestamps:
            if ts >= now - WORKSHOP_RATE_WINDOW:
                _WORKSHOP_LIMITER.append(ts)
        _permanent_failures.clear()
        _permanent_failures.update(config.dead_workshop_ids)


def _sync_workshop_limiter() -> None:
    with _workshop_lock:
        config.workshop_timestamps = list(_WORKSHOP_LIMITER)


def _workshop_limiter_state() -> tuple[int, Optional[float]]:
    with _workshop_lock:
        now = time.time()
        while _WORKSHOP_LIMITER and _WORKSHOP_LIMITER[0] < now - WORKSHOP_RATE_WINDOW:
            _WORKSHOP_LIMITER.popleft()
        count = len(_WORKSHOP_LIMITER)
        next_available = None
        if count >= WORKSHOP_RATE_LIMIT:
            next_available = _WORKSHOP_LIMITER[0] + WORKSHOP_RATE_WINDOW
        return count, next_available


def _prune_failures() -> None:
    with _workshop_lock:
        cutoff = time.time() - WORKSHOP_RETRY_COOLDOWN
        for ws_id in list(_failed_workshop_ids):
            if _failed_workshop_ids[ws_id] < cutoff:
                del _failed_workshop_ids[ws_id]


def _mark_pending(ws_id: str) -> None:
    with _workshop_lock:
        _pending_workshop_ids.add(ws_id)


def _unmark_pending(ws_id: str) -> None:
    with _workshop_lock:
        _pending_workshop_ids.discard(ws_id)


def _record_failure(ws_id: str, timestamp: float) -> None:
    with _workshop_lock:
        _failed_workshop_ids[ws_id] = timestamp


def _is_permanent_failure(ws_id: str) -> bool:
    with _workshop_lock:
        return ws_id in _permanent_failures


def _is_recent_failure(ws_id: str) -> bool:
    with _workshop_lock:
        return ws_id in _failed_workshop_ids


def _init_details_cache() -> None:
    global _workshop_details_cache
    with _workshop_lock:
        _workshop_details_cache.clear()
        try:
            if os.path.exists(DETAILS_CACHE_FILE):
                with open(DETAILS_CACHE_FILE) as f:
                    _workshop_details_cache.update(json.load(f))
        except (OSError, json.JSONDecodeError):
            _workshop_details_cache.clear()


def _save_details_cache() -> None:
    with _workshop_lock:
        try:
            os.makedirs(os.path.dirname(DETAILS_CACHE_FILE), exist_ok=True)
            with open(DETAILS_CACHE_FILE, "w") as f:
                json.dump(_workshop_details_cache, f)
        except OSError as exc:
            logger.log("error", f"Failed to save workshop details cache: {exc}")


def _get_details_from_cache(ws_id: str) -> Optional[dict]:
    with _workshop_lock:
        return _workshop_details_cache.get(ws_id)


def _set_details_in_cache(ws_id: str, data: dict) -> None:
    with _workshop_lock:
        _workshop_details_cache[ws_id] = {
            "time_created": data.get("time_created"),
            "time_updated": data.get("time_updated"),
        }


def _details_queue_length() -> int:
    with _workshop_lock:
        return len(_details_queue)


def _enqueue_details(ws_id: str) -> bool:
    with _workshop_lock:
        if ws_id in _details_queue or ws_id in _details_pending_ids:
            return False
        _details_queue.append(ws_id)
        return True


def _dequeue_details() -> Optional[str]:
    with _workshop_lock:
        return _details_queue.popleft() if _details_queue else None


def _discard_details_from_queue(ws_id: str) -> None:
    with _workshop_lock:
        if ws_id in _details_queue:
            _details_queue.remove(ws_id)


def _requeue_details(ws_id: str) -> None:
    with _workshop_lock:
        _details_queue.appendleft(ws_id)


def _mark_details_pending(ws_id: str) -> None:
    with _workshop_lock:
        _details_pending_ids.add(ws_id)


def _unmark_details_pending(ws_id: str) -> None:
    with _workshop_lock:
        _details_pending_ids.discard(ws_id)


def _check_workshop_rate_limit() -> bool:
    with _workshop_lock:
        now = time.time()
        while _WORKSHOP_LIMITER and _WORKSHOP_LIMITER[0] < now - WORKSHOP_RATE_WINDOW:
            _WORKSHOP_LIMITER.popleft()
        if len(_WORKSHOP_LIMITER) >= WORKSHOP_RATE_LIMIT:
            return False
        _WORKSHOP_LIMITER.append(now)
        return True


def _fetch_published_file_details(ws_id: str) -> dict:
    data = {"itemcount": 1, "publishedfileids[0]": ws_id}
    payload = urllib.parse.urlencode(data).encode()
    try:
        req = urllib.request.Request(
            "https://api.steampowered.com/ISteamRemoteStorage/GetPublishedFileDetails/v1/",
            data=payload,
            headers={"User-Agent": "IsaacMM/1.0"},
        )
        with urllib.request.urlopen(req, timeout=10, context=_ssl_context) as resp:
            result = json.loads(resp.read())
    except (urllib.error.URLError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"workshop {ws_id}: API request failed: {exc}")

    details = result.get("response", {}).get("publishedfiledetails", [])
    if not details:
        raise RuntimeError(f"workshop {ws_id}: no publishedfiledetails in API response")

    match details[0].get("result", 0):
        case 1:
            return details[0]
        case 9:
            raise FileNotFoundError(f"workshop {ws_id}: file not found (result=9)")
        case other:
            raise RuntimeError(
                f"workshop {ws_id}: API returned result={other} (expected 1)"
            )


def _fetch_workshop_preview_url(ws_id: str) -> str:
    details = _fetch_published_file_details(ws_id)
    preview_url = details.get("preview_url", "")
    if not preview_url:
        raise RuntimeError(f"workshop {ws_id}: empty preview_url in API response")
    return preview_url


def _scrape_workshop_dates(ws_id: str) -> dict:
    url = f"https://steamcommunity.com/sharedfiles/filedetails/?id={ws_id}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "IsaacMM/1.0"})
        with urllib.request.urlopen(req, timeout=10, context=_ssl_context) as resp:
            html = resp.read().decode("utf-8", errors="replace")
    except (urllib.error.URLError, OSError):
        return {"time_created": None, "time_updated": None}

    vals = re.findall(
        r'<div class="detailsStatRight">([^<]+)</div>', html
    )
    try:
        time_created = datetime.strptime(
            vals[1].strip(), "%d %b, %Y @ %I:%M%p"
        ).timestamp()
    except (IndexError, ValueError):
        time_created = None

    time_updated = None
    if len(vals) >= 3:
        try:
            time_updated = datetime.strptime(
                vals[2].strip(), "%d %b, %Y @ %I:%M%p"
            ).timestamp()
        except (ValueError):
            pass

    return {"time_created": time_created, "time_updated": time_updated}


def _fetch_workshop_details(ws_id: str) -> dict:
    try:
        details = _fetch_published_file_details(ws_id)
    except FileNotFoundError:
        return _scrape_workshop_dates(ws_id)
    return {
        "time_created": details.get("time_created"),
        "time_updated": details.get("time_updated"),
    }


def _download_workshop_icon(ws_id: str, cached_path: str) -> str:
    if not _check_workshop_rate_limit():
        raise RuntimeError("rate_limited")

    try:
        preview_url = _fetch_workshop_preview_url(ws_id)

        req_img = urllib.request.Request(
            preview_url, headers={"User-Agent": "IsaacMM/1.0"}
        )
        with urllib.request.urlopen(
            req_img, timeout=10, context=_ssl_context
        ) as resp_img:
            img_data = resp_img.read()
            content_type = resp_img.headers.get("Content-Type", "")

        os.makedirs(os.path.dirname(cached_path), exist_ok=True)

        ext = ".gif" if "gif" in content_type else ".png"
        actual_path = cached_path.rsplit(".", 1)[0] + ext
        with open(actual_path, "wb") as f:
            f.write(img_data)

        return actual_path
    except FileNotFoundError:
        with _workshop_lock:
            _permanent_failures.add(ws_id)
            config.dead_workshop_ids = sorted(_permanent_failures)
        config.save()
        raise RuntimeError(f"workshop {ws_id}: file not found (permanent)")
    except urllib.error.HTTPError as exc:
        if exc.code == 429:
            with _workshop_lock:
                now = time.time()
                for _ in range(WORKSHOP_RATE_LIMIT):
                    _WORKSHOP_LIMITER.append(now)
            raise RuntimeError("rate_limited")
        raise RuntimeError(f"workshop {ws_id}: image download failed: {exc}")
    except Exception as exc:
        raise RuntimeError(f"workshop {ws_id}: {exc}")
