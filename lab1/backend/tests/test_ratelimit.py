from app.ratelimit import SlidingWindowRateLimiter


def test_blocks_after_limit():
    rl = SlidingWindowRateLimiter(limit_per_minute=2)
    assert rl.check("a", now=0.0) is True
    assert rl.check("a", now=1.0) is True
    assert rl.check("a", now=2.0) is False


def test_independent_keys():
    rl = SlidingWindowRateLimiter(limit_per_minute=1)
    assert rl.check("a", now=0.0) is True
    assert rl.check("b", now=0.5) is True


def test_window_slides():
    rl = SlidingWindowRateLimiter(limit_per_minute=1)
    assert rl.check("a", now=0.0) is True
    assert rl.check("a", now=30.0) is False
    assert rl.check("a", now=61.0) is True
