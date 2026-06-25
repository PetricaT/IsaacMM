import json
import os
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import deque
from typing import Optional, Tuple

from .. import config, logger, paths

_ssl_context = ssl.create_default_context()

_WORKSHOP_LIMITER: deque = deque()
WORKSHOP_RATE_LIMIT: int = 5
WORKSHOP_RATE_WINDOW: int = 600
WORKSHOP_RETRY_COOLDOWN: int = 600
_failed_workshop_ids: dict[str, float] = {}
_permanent_failures: set[str] = set()
_pending_workshop_ids: set[str] = set()
_workshop_queue: deque[tuple[str, str]] = deque()



def _workshop_queue_length() -> int:
    return len(_workshop_queue)


def _enqueue_workshop(ws_id: str, normalized_name: str) -> bool:
    for wid, _ in _workshop_queue:
        if wid == ws_id:
            return False
    if ws_id in _pending_workshop_ids:
        return False
    _workshop_queue.append((ws_id, normalized_name))
    return True


def _dequeue_workshop() -> Optional[tuple[str, str]]:
    return _workshop_queue.popleft() if _workshop_queue else None


def _discard_from_queue(ws_id: str) -> None:
    for i, (wid, _) in enumerate(_workshop_queue):
        if wid == ws_id:
            del _workshop_queue[i]
            break


def _requeue_workshop(ws_id: str, normalized_name: str) -> None:
    _workshop_queue.appendleft((ws_id, normalized_name))


def _init_workshop_limiter() -> None:
    now = time.time()
    _WORKSHOP_LIMITER.clear()
    for ts in config.workshop_timestamps:
        if ts >= now - WORKSHOP_RATE_WINDOW:
            _WORKSHOP_LIMITER.append(ts)
    _permanent_failures.clear()
    _permanent_failures.update(config.dead_workshop_ids)


def _sync_workshop_limiter() -> None:
    config.workshop_timestamps = list(_WORKSHOP_LIMITER)


def _workshop_limiter_state() -> tuple[int, Optional[float]]:
    now = time.time()
    while _WORKSHOP_LIMITER and _WORKSHOP_LIMITER[0] < now - WORKSHOP_RATE_WINDOW:
        _WORKSHOP_LIMITER.popleft()
    count = len(_WORKSHOP_LIMITER)
    next_available = None
    if count >= WORKSHOP_RATE_LIMIT:
        next_available = _WORKSHOP_LIMITER[0] + WORKSHOP_RATE_WINDOW
    return count, next_available


def _prune_failures() -> None:
    cutoff = time.time() - WORKSHOP_RETRY_COOLDOWN
    for ws_id in list(_failed_workshop_ids):
        if _failed_workshop_ids[ws_id] < cutoff:
            del _failed_workshop_ids[ws_id]


def _check_workshop_rate_limit() -> bool:
    now = time.time()
    while _WORKSHOP_LIMITER and _WORKSHOP_LIMITER[0] < now - WORKSHOP_RATE_WINDOW:
        _WORKSHOP_LIMITER.popleft()
    if len(_WORKSHOP_LIMITER) >= WORKSHOP_RATE_LIMIT:
        return False
    _WORKSHOP_LIMITER.append(now)
    return True


def _fetch_workshop_preview_url(ws_id: str) -> str:
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
            return details[0]["preview_url"]
        case 9:
            raise FileNotFoundError(f"workshop {ws_id}: file not found (result=9)")
        case other:
            raise RuntimeError(f"workshop {ws_id}: API returned result={other} (expected 1)")


def _download_workshop_icon(ws_id: str, cached_path: str) -> str:
    if not _check_workshop_rate_limit():
        raise RuntimeError("rate_limited")

    try:
        preview_url = _fetch_workshop_preview_url(ws_id)

        req_img = urllib.request.Request(
            preview_url, headers={"User-Agent": "IsaacMM/1.0"}
        )
        with urllib.request.urlopen(req_img, timeout=10, context=_ssl_context) as resp_img:
            img_data = resp_img.read()

        os.makedirs(os.path.dirname(cached_path), exist_ok=True)
        with open(cached_path, "wb") as f:
            f.write(img_data)

        return ws_id
    except FileNotFoundError:
        _permanent_failures.add(ws_id)
        config.dead_workshop_ids = sorted(_permanent_failures)
        config.save()
        raise RuntimeError(f"workshop {ws_id}: file not found (permanent)")
    except urllib.error.HTTPError as exc:
        if exc.code == 429:
            now = time.time()
            for _ in range(WORKSHOP_RATE_LIMIT):
                _WORKSHOP_LIMITER.append(now)
            raise RuntimeError("rate_limited")
        raise RuntimeError(f"workshop {ws_id}: image download failed: {exc}")
    except Exception as exc:
        raise RuntimeError(f"workshop {ws_id}: {exc}")
