"""Generic remote data cache with fetch/cache/bundled/fallback chain."""

from __future__ import annotations

import os
import threading
from datetime import datetime, timedelta
from typing import Any, Callable, Optional

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from . import logger


class RemoteCache:
    _HEADERS = {"User-Agent": "IsaacMM/1.0"}

    def __init__(
        self,
        url: str,
        cache_path: str,
        bundled_path: str,
        ttl: timedelta,
        parse_fn: Callable[[str], Any],
        fallback: Any,
        on_http_error: Optional[Callable[[httpx.HTTPStatusError], None]] = None,
    ) -> None:
        self._url = url
        self._cache_path = cache_path
        self._bundled_path = bundled_path
        self._ttl = ttl
        self._parse_fn = parse_fn
        self._fallback = fallback
        self._on_http_error = on_http_error
        self._data: Optional[Any] = None
        self._lock = threading.Lock()

    def _is_fresh(self) -> bool:
        try:
            if not os.path.exists(self._cache_path):
                return False
            mtime = datetime.fromtimestamp(os.path.getmtime(self._cache_path))
            return datetime.now() - mtime <= self._ttl
        except OSError:
            return False

    def _try_fetch(self) -> Optional[Any]:
        try:
            raw = self._http_get_text(self._url)
            data = self._parse_fn(raw)
            os.makedirs(os.path.dirname(self._cache_path), exist_ok=True)
            with open(self._cache_path, "w", encoding="utf-8") as f:
                f.write(raw)
            return data
        except httpx.HTTPStatusError as exc:
            if self._on_http_error:
                self._on_http_error(exc)
            return None
        except httpx.RequestError:
            logger.log("warning", f"No network, cannot fetch {self._url}")
            return None
        except (OSError, ValueError) as exc:
            logger.log("error", f"Error loading {self._url}: {exc}")
            return None

    def _try_cache(self) -> Optional[Any]:
        try:
            with open(self._cache_path, encoding="utf-8") as f:
                return self._parse_fn(f.read())
        except OSError, ValueError:
            return None

    def _try_bundled(self) -> Optional[Any]:
        try:
            with open(self._bundled_path, encoding="utf-8") as f:
                return self._parse_fn(f.read())
        except OSError, ValueError:
            return None

    def get(self) -> Any:
        with self._lock:
            if self._data is not None:
                return self._data
            data = None
            if self._is_fresh():
                data = self._try_cache()
            if data is None:
                data = self._try_fetch()
            if data is None:
                data = self._try_cache()
            if data is None:
                data = self._try_bundled()
            self._data = data if data is not None else self._fallback
            return self._data

    def fetch_background(self) -> Optional[bool]:
        with self._lock:
            if self._is_fresh():
                return None
            data = self._try_fetch()
            if data is not None:
                self._data = data
                return True
            return False

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(min=1, max=10),
        retry=retry_if_exception_type(httpx.RequestError),
        reraise=True,
    )
    def _http_get_text(self, url: str) -> str:
        with httpx.Client(follow_redirects=True) as client:
            resp = client.get(url, headers=self._HEADERS, timeout=10)
            resp.raise_for_status()
            return resp.text
