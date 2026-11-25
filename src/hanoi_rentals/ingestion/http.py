"""Bounded public HTTP retrieval with explicit rate limits and challenge detection."""

import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

from curl_cffi import requests

from hanoi_rentals.features.dates import ZONE


class FetchError(RuntimeError):
    def __init__(
        self, kind, url, *, status=None, attempts=1, retry_after=None, body=""
    ):
        super().__init__(f"{kind}: HTTP {status or 'network error'}: {url}")
        self.kind = kind
        self.url = url
        self.status = status
        self.attempts = attempts
        self.retry_after = retry_after
        self.body = body


def retry_delay(value):
    if not value:
        return None
    try:
        return max(0.0, float(value))
    except ValueError:
        try:
            when = parsedate_to_datetime(value)
            if when.tzinfo is None:
                when = when.replace(tzinfo=timezone.utc)
            return max(0.0, (when - datetime.now(timezone.utc)).total_seconds())
        except (ValueError, TypeError, OverflowError):
            return None


def is_challenge(body):
    text = body.lower()
    if not text.lstrip().startswith("<"):
        return False
    return any(
        marker in text
        for marker in (
            "xác minh không phải robot",
            "verify you are human",
            "verify that you are human",
            "cf-chl-",
            "g-recaptcha",
            "h-captcha",
        )
    )


def fetch(session, url, params=None, *, attempts=3, sleep=time.sleep):
    for attempt in range(1, attempts + 1):
        try:
            response = session.get(url, params=params, timeout=35)
        except requests.exceptions.RequestException as exc:
            if attempt == attempts:
                raise FetchError("network_error", url, attempts=attempt) from exc
            sleep(5 * attempt)
            continue
        body = response.text
        status = response.status_code
        delay = retry_delay(response.headers.get("Retry-After"))
        # A verification page is not data, including when served with HTTP 200.
        if is_challenge(body) and (
            status != 200
            or "article.property-item" not in body
            and "property-item" not in body
        ):
            raise FetchError(
                "verification_required",
                response.url,
                status=status,
                attempts=attempt,
                retry_after=delay,
                body=body,
            )
        if status == 200:
            return body, {
                "request_url": response.url,
                "http_status": status,
                "http_attempts": attempt,
                "collected_at": datetime.now(ZONE).isoformat(),
            }
        if status in (401, 403):
            raise FetchError(
                "access_denied",
                response.url,
                status=status,
                attempts=attempt,
                body=body,
            )
        if status not in (429, 500, 502, 503, 504):
            raise FetchError(
                "http_error", response.url, status=status, attempts=attempt, body=body
            )
        wait = delay if delay is not None else (60 if status == 429 else 10) * attempt
        if attempt == attempts or wait > 60:
            raise FetchError(
                "rate_limited" if status == 429 else "server_error",
                response.url,
                status=status,
                attempts=attempt,
                retry_after=wait,
                body=body,
            )
        sleep(wait)
    raise AssertionError("Retry loop exited without a result")
