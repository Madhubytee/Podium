"""Rate limiting.

Analysis is CPU heavy and live mode spends money on OpenAI, so each user gets a
budget per action. Limits are sliding windows kept in memory, which is right
for one server process; move to Redis if we ever run several.

Supabase already rate limits sign in and sign up on its side.
"""

import math
import os
import threading
import time
from collections import defaultdict, deque

from fastapi import Depends, HTTPException, Request

from .auth import User, current_user

# action -> (max requests, window seconds)
LIMITS = {
    "rehearsal": (30, 3600),      # new rehearsals
    "files": (30, 3600),          # resume / slides / script uploads
    "take": (40, 3600),           # new takes
    "upload": (15, 3600),         # recordings sent for analysis
    "oli": (60, 600),             # live mode messages that call ChatGPT or Whisper
    "media": (300, 600),          # clips and video
    "ip": (240, 60),              # every API request, per IP address
}
MAX_PROCESSING_PER_USER = int(os.getenv("PODIUM_MAX_PROCESSING_PER_USER", "2"))


class RateLimited(Exception):
    def __init__(self, retry_after: float):
        self.retry_after = max(1, math.ceil(retry_after))
        super().__init__(message(self.retry_after))


def message(seconds: int) -> str:
    wait = f"{seconds} seconds" if seconds < 90 else f"{math.ceil(seconds / 60)} minutes"
    return f"Slow down a little: try again in {wait}."


class Limiter:
    def __init__(self, limits: dict[str, tuple[int, int]]):
        self.limits = limits
        self._hits: dict[tuple[str, str], deque] = defaultdict(deque)
        self._lock = threading.Lock()

    def hit(self, action: str, key: str) -> None:
        """Record one request; raise RateLimited when over the limit."""
        if os.getenv("PODIUM_RATE_LIMITS", "on") == "off":
            return
        limit, window = self.limits[action]
        now = time.monotonic()
        with self._lock:
            q = self._hits[(action, key)]
            while q and now - q[0] >= window:
                q.popleft()
            if len(q) >= limit:
                raise RateLimited(window - (now - q[0]))
            q.append(now)

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()


limiter = Limiter(LIMITS)


def http_error(exc: RateLimited) -> HTTPException:
    return HTTPException(429, str(exc), headers={"Retry-After": str(exc.retry_after)})


def limit(action: str):
    """FastAPI dependency: count this request against the signed in user's budget."""
    def dependency(user: User = Depends(current_user)) -> User:
        try:
            limiter.hit(action, f"user:{user.id}")
        except RateLimited as exc:
            raise http_error(exc)
        return user
    return dependency


def client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"
