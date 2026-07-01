"""Generic remote data cache with fetch/cache/bundled/fallback chain."""
from __future__ import annotations


import os
import ssl
import threading
from datetime import datetime, timedelta
from typing import Any, Callable, Optional
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from . import logger


class RemoteCache:
    def __init__(
        self,
        url: str,
        cache_path: str,
        bundled_path: str,
        ttl: timedelta,
        parse_fn: Callable[[str], Any],
        fallback: Any,
        on_http_error: Optional[Callable[[HTTPError], None]] = None,
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
        self._ssl_context = ssl.create_default_context()

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
            req = Request(self._url, headers={"User-Agent": "IsaacMM/1.0"})
            with urlopen(req, timeout=10, context=self._ssl_context) as resp:
                raw = resp.read().decode("utf-8")
            data = self._parse_fn(raw)
            os.makedirs(os.path.dirname(self._cache_path), exist_ok=True)
            with open(self._cache_path, "w") as f:
                f.write(raw)
            return data
        except HTTPError as exc:
            if self._on_http_error:
                self._on_http_error(exc)
            return None
        except URLError:
            logger.log("warning", f"No network, cannot fetch {self._url}")
            return None
        except (OSError, ValueError) as exc:
            logger.log("error", f"Error loading {self._url}: {exc}")
            return None

    def _try_cache(self) -> Optional[Any]:
        try:
            with open(self._cache_path) as f:
                return self._parse_fn(f.read())
        except (OSError, ValueError):
            return None

    def _try_bundled(self) -> Optional[Any]:
        try:
            with open(self._bundled_path) as f:
                return self._parse_fn(f.read())
        except (OSError, ValueError):
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
