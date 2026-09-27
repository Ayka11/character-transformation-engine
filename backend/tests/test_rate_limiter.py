from cte.observability import SlidingWindowRateLimiter


def test_sliding_window_allows_until_limit():
    limiter=SlidingWindowRateLimiter(2,window_seconds=60)
    assert limiter.allow("client",now=0)==(True,0)
    assert limiter.allow("client",now=1)==(True,0)
    allowed,retry=limiter.allow("client",now=2)
    assert allowed is False
    assert retry>0


def test_sliding_window_expires_old_requests():
    limiter=SlidingWindowRateLimiter(1,window_seconds=60)
    assert limiter.allow("client",now=0)==(True,0)
    assert limiter.allow("client",now=59)[0] is False
    assert limiter.allow("client",now=61)==(True,0)


def test_rate_limiter_keys_are_isolated():
    limiter=SlidingWindowRateLimiter(1,window_seconds=60)
    assert limiter.allow("a",now=0)==(True,0)
    assert limiter.allow("a",now=1)[0] is False
    assert limiter.allow("b",now=1)==(True,0)
