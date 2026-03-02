from __future__ import annotations


def explain_gemini_exception(exc: Exception, stage: str) -> str:
    raw = str(exc).strip() or exc.__class__.__name__
    text = raw.lower()

    auth_tokens = [
        "api key",
        "invalid api key",
        "invalid key",
        "unauthenticated",
        "permission denied",
        "forbidden",
        "401",
        "403",
        "credentials",
        "api_key",
    ]
    quota_tokens = [
        "quota",
        "resource_exhausted",
        "rate limit",
        "429",
        "too many requests",
        "exceeded",
    ]
    network_tokens = [
        "timeout",
        "timed out",
        "connection",
        "network",
        "temporarily unavailable",
    ]

    if any(token in text for token in auth_tokens):
        return (
            f"{stage} failed: Gemini authentication error. "
            f"Check GOOGLE_API_KEY and API permissions. Details: {raw}"
        )
    if any(token in text for token in quota_tokens):
        return (
            f"{stage} failed: Gemini quota or rate limit reached. "
            f"Check quota/billing and retry later. Details: {raw}"
        )
    if any(token in text for token in network_tokens):
        return f"{stage} failed: Gemini network/timeout issue. Retry later. Details: {raw}"
    return f"{stage} failed: Gemini API error. Details: {raw}"


def is_transient_overload_error(exc_or_text: Exception | str) -> bool:
    text = str(exc_or_text).lower()
    tokens = [
        "503",
        "unavailable",
        "high demand",
        "temporarily unavailable",
        "deadline exceeded",
        "timeout",
        "timed out",
        "connection reset",
    ]
    return any(token in text for token in tokens)


def is_model_not_found_error(exc_or_text: Exception | str) -> bool:
    text = str(exc_or_text).lower()
    return (
        "404" in text
        and "model" in text
        and ("not found" in text or "unknown model" in text or "not supported" in text)
    )


def explain_empty_response(stage: str) -> str:
    return (
        f"{stage} failed: Gemini returned an empty response. "
        "This may be caused by quota limits, safety filtering, or transient API issues."
    )


def print_once(cache: set[str], message: str, prefix: str) -> None:
    key = f"{prefix}::{message}"
    if key in cache:
        return
    cache.add(key)
    print(f"[{prefix}] ERROR: {message}")
