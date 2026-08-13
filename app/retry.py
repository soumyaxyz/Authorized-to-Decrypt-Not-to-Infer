"""Shared retry helper for calls to other containers over Docker's network.

Docker Desktop's embedded DNS on this host is intermittently flaky --
observed hitting essentially every hostname used in this project at one
point or another (ipfs, individual chain aliases, besu peer aliases, the
CA), always transient, always resolves on a later retry, but occasionally
takes longer than a few seconds to clear. Not tied to container age or any
particular piece of code -- retrying generously here is cheaper than
debugging a phantom outage each time it recurs.
"""

import time


def with_retry(fn, attempts: int = 30, delay: float = 3.0):
    last_exc = None
    for attempt in range(attempts):
        try:
            return fn()
        except Exception as exc:
            last_exc = exc
            if attempt < attempts - 1:
                time.sleep(delay)
    raise last_exc
