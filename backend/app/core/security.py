import hashlib
import hmac
import logging
import time
from typing import Optional

from app.core.redis_client import RedisCache

logger = logging.getLogger(__name__)
cache = RedisCache()


class RateLimiter:
    def __init__(self, max_requests: int = 30, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds

    async def is_allowed(self, user_id: int, action: str = "default") -> bool:
        key = f"rate:{action}:{user_id}"
        count = await cache.incr(key, self.window_seconds)
        return count <= self.max_requests


def verify_plisio_signature(data: dict, secret: str) -> bool:
    """Verify Plisio webhook signature."""
    verify_hash = data.pop("verify_hash", None)
    if not verify_hash:
        return False
    sorted_items = sorted(data.items())
    sign_string = "|".join(str(v) for _, v in sorted_items)
    expected = hmac.new(
        secret.encode(),
        sign_string.encode(),
        hashlib.sha1,
    ).hexdigest()
    return hmac.compare_digest(expected, verify_hash)


async def check_spam(user_id: int, cooldown: int = 2) -> bool:
    """Return True if user is spamming (too fast)."""
    key = f"spam:{user_id}"
    last = await cache.get(key)
    now = time.time()
    if last and (now - float(last)) < cooldown:
        return True
    await cache.set(key, str(now), ttl=cooldown)
    return False
