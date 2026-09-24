"""Cooperative task cancellation, distinct from service shutdown and failures."""


class JobCancelled(BaseException):
    """Stop at a safe boundary without triggering fallback or paid retries.

    This is intentionally not an Exception: best-effort retrieval and repair
    handlers must not swallow an explicit user cancellation.
    """

