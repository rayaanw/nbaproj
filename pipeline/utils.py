"""Shared helpers for the offline pipeline scripts.

Centralizes the retry/backoff/politeness logic used by every `nba_api`
puller (T-005, T-006, T-007) so each script only has to describe *what*
to fetch, not *how* to fetch it resiliently.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Callable, TypeVar

from pipeline.config import MAX_RETRIES, REQUEST_DELAY_SECONDS

T = TypeVar("T")


def call_with_retry(
    build_endpoint: Callable[[], T],
    *,
    max_retries: int = MAX_RETRIES,
    delay_seconds: float = REQUEST_DELAY_SECONDS,
    description: str = "request",
) -> T:
    """Call `build_endpoint()` (an nba_api endpoint constructor, which makes
    the HTTP request as a side effect of `__init__` when get_request=True),
    retrying with exponential backoff on failure.

    Always sleeps `delay_seconds` after a *successful* call too, so callers
    don't need to remember to pace themselves between iterations — stats.nba.com
    rate-limits aggressively and a fixed delay is cheap insurance against IP
    throttling.
    """
    last_exc: Exception | None = None
    for attempt in range(1, max_retries + 1):
        try:
            result = build_endpoint()
            time.sleep(delay_seconds)
            return result
        except Exception as exc:  # noqa: BLE001 - deliberately broad: network/API errors vary widely
            last_exc = exc
            if attempt < max_retries:
                backoff = delay_seconds * (2 ** (attempt - 1))
                print(
                    f"  [retry {attempt}/{max_retries}] {description} failed "
                    f"({exc!r}); backing off {backoff:.1f}s"
                )
                time.sleep(backoff)
            else:
                print(f"  [failed] {description} failed after {max_retries} attempts: {exc!r}")
    assert last_exc is not None
    raise last_exc


def log_failure(log_path: Path, identifier: str, error: Exception) -> None:
    """Append a single failure line to a pipeline failures log.

    Creates the parent directory if needed. Used by T-005.5 / T-006.4 so a
    crashed/rate-limited run leaves a clear record of what still needs a
    manual re-run, without stopping the rest of the loop.
    """
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with open(log_path, "a") as f:
        f.write(f"{identifier}\t{error!r}\n")
