from __future__ import annotations

import time
from collections import defaultdict, deque


class SlidingWindowRateLimiter:
    def __init__(self, max_requests: int, window_seconds: int) -> None:
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.windows: dict[int, deque[float]] = defaultdict(deque)

    def is_limited(self, key: int) -> bool:
        now = time.monotonic()
        window = self.windows[key]

        while window and now - window[0] > self.window_seconds:
            window.popleft()

        if len(window) >= self.max_requests:
            return True

        window.append(now)
        return False
