"""In-memory rate limit: скользящее окно на ключ (IP)."""
import time
from collections import deque

WINDOW_SECONDS = 60.0


class SlidingWindowRateLimiter:
    def __init__(self, limit_per_minute: int) -> None:
        self.limit_per_minute = limit_per_minute
        self._hits: dict[str, deque[float]] = {}

    def check(self, key: str, now: float | None = None) -> bool:
        """True — запрос разрешён (и учитывается), False — лимит превышен."""
        if now is None:
            now = time.monotonic()
        hits = self._hits.setdefault(key, deque())
        while hits and now - hits[0] >= WINDOW_SECONDS:
            hits.popleft()
        if len(hits) >= self.limit_per_minute:
            return False
        hits.append(now)
        return True
