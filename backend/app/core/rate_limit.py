"""Process-local sliding-window rate limiter for auth abuse prevention.

Each API process enforces its own counters. That is enough to stop unbounded
credential stuffing and email bombing on a single task; multi-task deployments
still get a per-task ceiling (N × limit across the fleet).
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from threading import Lock
from time import monotonic

from starlette.requests import Request

from app.core.exceptions import RateLimitError
from app.core.request_meta import request_meta

_RATE_LIMIT_MESSAGE = "Too many requests. Try again later."


@dataclass(frozen=True, slots=True)
class RateLimitRule:
    """Max hits allowed inside a sliding window."""

    limit: int
    window_seconds: int


# Sensible defaults: tight on email issuance, looser on login/refresh.
LOGIN_IP = RateLimitRule(20, 900)
LOGIN_EMAIL = RateLimitRule(10, 900)
REGISTER_IP = RateLimitRule(10, 3600)
FORGOT_IP = RateLimitRule(10, 3600)
FORGOT_EMAIL = RateLimitRule(5, 3600)
TOKEN_IP = RateLimitRule(20, 900)  # reset-password + verify-email
RESEND_USER = RateLimitRule(5, 3600)
REFRESH_IP = RateLimitRule(60, 900)
VERIFY_EMAIL_ISSUE = RateLimitRule(5, 3600)


class SlidingWindowRateLimiter:
    """Thread-safe in-memory sliding window keyed by opaque strings."""

    def __init__(self) -> None:
        self._hits: dict[str, list[float]] = defaultdict(list)
        self._lock = Lock()

    def hit(self, key: str, rule: RateLimitRule) -> None:
        """Record one attempt; raise RateLimitError when the window is full."""
        now = monotonic()
        window_start = now - rule.window_seconds
        with self._lock:
            recent = [t for t in self._hits[key] if t > window_start]
            if len(recent) >= rule.limit:
                self._hits[key] = recent
                raise RateLimitError(_RATE_LIMIT_MESSAGE)
            recent.append(now)
            self._hits[key] = recent

    def reset(self) -> None:
        """Drop all counters (used between tests)."""
        with self._lock:
            self._hits.clear()


_limiter = SlidingWindowRateLimiter()


def get_rate_limiter() -> SlidingWindowRateLimiter:
    """Return the process-wide limiter singleton."""
    return _limiter


def reset_rate_limiter() -> None:
    """Clear all rate-limit counters (test isolation)."""
    _limiter.reset()


def enforce_rate_limit(key: str, rule: RateLimitRule) -> None:
    """Apply ``rule`` to ``key``, raising RateLimitError when exceeded."""
    _limiter.hit(key, rule)


def client_ip_subject(request: Request) -> str:
    """Stable per-client subject for IP-keyed auth buckets."""
    return request_meta(request).ip_address or "unknown"


def limit_login(request: Request, email: str) -> None:
    """Throttle login by client IP and by email (credential stuffing)."""
    enforce_rate_limit(f"auth:login:ip:{client_ip_subject(request)}", LOGIN_IP)
    enforce_rate_limit(f"auth:login:email:{email.lower()}", LOGIN_EMAIL)


def limit_register(request: Request) -> None:
    """Throttle account creation by client IP."""
    enforce_rate_limit(f"auth:register:ip:{client_ip_subject(request)}", REGISTER_IP)


def limit_forgot_password(request: Request, email: str) -> None:
    """Throttle forgot-password by IP and email (email-bomb / enumeration)."""
    enforce_rate_limit(f"auth:forgot:ip:{client_ip_subject(request)}", FORGOT_IP)
    enforce_rate_limit(f"auth:forgot:email:{email.lower()}", FORGOT_EMAIL)


def limit_token_guess(request: Request, *, kind: str) -> None:
    """Throttle reset/verify token submission by client IP."""
    enforce_rate_limit(f"auth:{kind}:ip:{client_ip_subject(request)}", TOKEN_IP)


def limit_refresh(request: Request) -> None:
    """Throttle refresh-token exchange by client IP."""
    enforce_rate_limit(f"auth:refresh:ip:{client_ip_subject(request)}", REFRESH_IP)


def limit_resend_verification(user_id: int) -> None:
    """Throttle verification re-sends per signed-in user."""
    enforce_rate_limit(f"auth:resend:user:{user_id}", RESEND_USER)


def limit_verification_email_issue(email: str) -> None:
    """Cap outbound verification emails per address (register + resend)."""
    enforce_rate_limit(f"auth:verify_email:email:{email.lower()}", VERIFY_EMAIL_ISSUE)
