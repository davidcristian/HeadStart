"""Generic adapter registry shared by the AI provider families.

Every AI family (summarizers, resumes, cover_letters, email_classifiers,
reply_drafters) resolves provider adapters the same way: a decorator to
self-register by key, a lazy import of the family's `adapters` package to
trigger registration, and a lookup that instantiates the adapter. That wiring
used to be copy-pasted into each family's `base.py`; it now lives here once.

A family creates one `AdapterRegistry` and re-exports its bound methods as the
familiar module-level `register_*` / `get_* ` / `available_*` functions, so
adding a provider stays a one-file change reached only through the registry.
"""

from __future__ import annotations

import importlib
from collections.abc import Callable
from typing import Any


class AdapterRegistry[T]:
    """Key -> adapter-class registry with lazy discovery and instantiation."""

    def __init__(self, *, noun: str, adapters_module: str) -> None:
        self._noun = noun
        self._adapters_module = adapters_module
        self._registry: dict[str, type[T]] = {}

    def register(self, key: str) -> Callable[[type[T]], type[T]]:
        """Decorator that self-registers an adapter class under `key`."""

        def decorator(cls: type[T]) -> type[T]:
            existing = self._registry.get(key)
            if existing is not None and existing is not cls:
                raise ValueError(f"{self._noun} key '{key}' is already registered.")
            self._registry[key] = cls
            return cls

        return decorator

    def get(self, key: str, *, settings: Any | None = None) -> T:
        """Instantiate the adapter registered under `key`."""
        self._discover()
        try:
            cls = self._registry[key]
        except KeyError as exc:
            raise KeyError(
                f"No {self._noun} registered for '{key}'. Available: {sorted(self._registry)}"
            ) from exc
        if settings is None:
            return cls()
        return cls(settings=settings)  # type: ignore[call-arg]

    def available(self) -> list[str]:
        """List registered keys (importing the adapters package first)."""
        self._discover()
        return sorted(self._registry)

    def _discover(self) -> None:
        importlib.import_module(self._adapters_module)  # noqa: F401  (triggers registration)
