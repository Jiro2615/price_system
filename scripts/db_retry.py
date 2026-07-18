import os
import time
from typing import Any, Callable, TypeVar

import psycopg


T = TypeVar("T")

DB_RETRY_EXIT_CODE = 75
DEFAULT_DB_RETRY_DELAYS = (5, 15, 30, 60, 120)
DEFAULT_DB_RETRY_MAX_ATTEMPTS = len(DEFAULT_DB_RETRY_DELAYS) + 1
DEFAULT_DB_RETRY_MAX_WAIT_SECONDS = sum(DEFAULT_DB_RETRY_DELAYS)


def _parse_positive_int(name: str, default: int) -> int:
    value = os.getenv(name, "").strip()
    if not value:
        return default
    try:
        parsed = int(value)
    except ValueError:
        return default
    return parsed if parsed > 0 else default


def get_db_retry_config() -> dict[str, Any]:
    return {
        "delays": DEFAULT_DB_RETRY_DELAYS,
        "max_attempts": _parse_positive_int(
            "PRICE_SYSTEM_DB_RETRY_MAX_ATTEMPTS",
            DEFAULT_DB_RETRY_MAX_ATTEMPTS,
        ),
        "max_wait_seconds": _parse_positive_int(
            "PRICE_SYSTEM_DB_RETRY_MAX_WAIT_SECONDS",
            DEFAULT_DB_RETRY_MAX_WAIT_SECONDS,
        ),
    }


def get_retryable_db_exceptions() -> tuple[type[BaseException], ...]:
    return tuple(
        exc
        for exc in (
            psycopg.OperationalError,
            psycopg.InterfaceError,
            getattr(psycopg.errors, "ConnectionTimeout", None),
            getattr(psycopg.errors, "ConnectionException", None),
            getattr(psycopg.errors, "AdminShutdown", None),
            getattr(psycopg.errors, "CrashShutdown", None),
            getattr(psycopg.errors, "CannotConnectNow", None),
        )
        if exc is not None
    )


RETRYABLE_DB_EXCEPTIONS = get_retryable_db_exceptions()


class TemporaryDbError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        attempts: int,
        waited_seconds: float,
        last_error: BaseException,
    ) -> None:
        super().__init__(message)
        self.attempts = attempts
        self.waited_seconds = waited_seconds
        self.last_error = last_error


def is_retryable_db_error(error: BaseException) -> bool:
    current: BaseException | None = error
    seen: set[int] = set()
    while current is not None and id(current) not in seen:
        if isinstance(current, RETRYABLE_DB_EXCEPTIONS):
            return True
        seen.add(id(current))
        current = current.__cause__ or current.__context__
    return False


def run_with_db_retry(
    operation: Callable[[], T],
    *,
    description: str,
    logger: Callable[[str], None],
    sleep_func: Callable[[float], None] = time.sleep,
    max_attempts: int | None = None,
    max_wait_seconds: int | None = None,
) -> T:
    config = get_db_retry_config()
    delays = tuple(config["delays"])
    max_attempts = max_attempts or int(config["max_attempts"])
    max_wait_seconds = (
        int(config["max_wait_seconds"])
        if max_wait_seconds is None
        else max_wait_seconds
    )
    attempts = 0
    waited_seconds = 0.0

    while True:
        attempts += 1
        try:
            return operation()
        except Exception as error:
            if not is_retryable_db_error(error):
                raise

            next_delay = delays[min(attempts - 1, len(delays) - 1)] if delays else 0
            can_retry_by_count = attempts < max_attempts
            can_retry_by_wait = (waited_seconds + next_delay) <= max_wait_seconds
            if not can_retry_by_count or not can_retry_by_wait:
                raise TemporaryDbError(
                    f"{description} failed after DB retries",
                    attempts=attempts,
                    waited_seconds=waited_seconds,
                    last_error=error,
                ) from error

            logger(
                f"db_retry description={description} attempt={attempts} "
                f"wait_seconds={next_delay} error={error.__class__.__name__}: {error}"
            )
            sleep_func(next_delay)
            waited_seconds += next_delay
