"""Portable Result monad and DomainError protocol per §10/§24 of Cláusulas Pétreas.

This module provides the canonical implementation of the Result pattern
prescribed by the clauses. Copy this file into any project's src/shared/
directory to bootstrap the pattern.

Usage:
    from shared.result import Success, Failure, Result

    def divide(a: float, b: float) -> Result[float, str]:
        if b == 0:
            return Failure("division by zero")
        return Success(a / b)

    result = divide(10, 3).map(round).and_then(validate)
    match result:
        case Success(value):
            print(f"Got {value}")
        case Failure(error):
            print(f"Error: {error}")
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import (
    Any,
    Callable,
    Generic,
    Protocol,
    TypeVar,
    Union,
    runtime_checkable,
)

T = TypeVar("T")
U = TypeVar("U")
E = TypeVar("E")
F = TypeVar("F")


# ── DomainError Protocol ────────────────────────────────────────────


@runtime_checkable
class DomainError(Protocol):
    """Protocol for domain-level errors.

    All domain errors must expose a code and a human-readable message.
    Optionally, they can carry context for structured logging.

    Example:
        @dataclass(frozen=True)
        class NotFoundError:
            entity: str
            entity_id: str

            @property
            def code(self) -> str:
                return "NOT_FOUND"

            @property
            def message(self) -> str:
                return f"{self.entity} '{self.entity_id}' not found"

            @property
            def context(self) -> dict[str, Any]:
                return {"entity": self.entity, "id": self.entity_id}
    """

    @property
    def code(self) -> str: ...

    @property
    def message(self) -> str: ...

    @property
    def context(self) -> dict[str, Any]:
        """Optional structured context for logging/telemetry."""
        return {}


# ── Result Types ─────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class Success(Generic[T]):
    """Represents a successful computation result."""

    value: T

    def is_success(self) -> bool:
        return True

    def is_failure(self) -> bool:
        return False

    def map(self, fn: Callable[[T], U]) -> Result[U, Any]:
        """Apply a function to the success value."""
        return Success(fn(self.value))

    def map_error(self, fn: Callable[[Any], F]) -> Result[T, F]:
        """No-op on Success — returns self unchanged."""
        return self  # type: ignore[return-value]

    def and_then(self, fn: Callable[[T], Result[U, Any]]) -> Result[U, Any]:
        """Chain a function that returns a Result."""
        return fn(self.value)

    def unwrap(self) -> T:
        """Extract the value, raising if Failure (never happens here)."""
        return self.value

    def unwrap_or(self, default: T) -> T:  # type: ignore[override]
        """Return the value (ignores default)."""
        return self.value

    def unwrap_or_else(self, fn: Callable[[Any], T]) -> T:
        """Return the value (ignores fallback)."""
        return self.value


@dataclass(frozen=True, slots=True)
class Failure(Generic[E]):
    """Represents a failed computation result."""

    error: E

    def is_success(self) -> bool:
        return False

    def is_failure(self) -> bool:
        return True

    def map(self, fn: Callable[[Any], Any]) -> Result[Any, E]:
        """No-op on Failure — returns self unchanged."""
        return self  # type: ignore[return-value]

    def map_error(self, fn: Callable[[E], F]) -> Result[Any, F]:
        """Apply a function to the error value."""
        return Failure(fn(self.error))

    def and_then(self, fn: Callable[[Any], Result[Any, E]]) -> Result[Any, E]:
        """No-op on Failure — returns self unchanged."""
        return self  # type: ignore[return-value]

    def unwrap(self) -> Any:
        """Raises ValueError since this is a Failure."""
        raise ValueError(f"Called unwrap() on Failure: {self.error}")

    def unwrap_or(self, default: T) -> T:
        """Return the default value."""
        return default

    def unwrap_or_else(self, fn: Callable[[E], T]) -> T:
        """Compute a fallback from the error."""
        return fn(self.error)


# ── Result Type Alias ────────────────────────────────────────────────

Result = Union[Success[T], Failure[E]]
"""A Result is either a Success[T] or a Failure[E].

Convention:
    - Functions that can fail return Result[ValueType, ErrorType]
    - Use .map() / .and_then() for chaining
    - Use match/case for exhaustive handling
"""


# ── Utility Functions ────────────────────────────────────────────────


def collect_results(results: list[Result[T, E]]) -> Result[list[T], E]:
    """Collect a list of Results into a Result of list.

    Returns a Failure at the first error encountered, or a
    Success containing all values if all succeeded.

    Example:
        results = [Success(1), Success(2), Success(3)]
        assert collect_results(results) == Success([1, 2, 3])

        results = [Success(1), Failure("oops"), Success(3)]
        assert collect_results(results) == Failure("oops")
    """
    values: list[T] = []
    for r in results:
        match r:
            case Success(value):
                values.append(value)
            case Failure():
                return r  # type: ignore[return-value]
    return Success(values)


def try_result(fn: Callable[..., T], *args: Any, **kwargs: Any) -> Result[T, Exception]:
    """Wrap a function call in a Result, catching exceptions.

    Example:
        result = try_result(int, "not_a_number")
        assert isinstance(result, Failure)
    """
    try:
        return Success(fn(*args, **kwargs))
    except Exception as exc:
        return Failure(exc)
