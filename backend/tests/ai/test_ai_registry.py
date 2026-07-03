from abc import ABC, abstractmethod

import pytest

from app.ai.registry import AdapterRegistry


class _Widget(ABC):
    @abstractmethod
    def run(self) -> str: ...


def _fresh() -> AdapterRegistry[_Widget]:
    # adapters_module points at a real, side-effect-free module so _discover()
    # imports something importable; registration here is done directly instead.
    return AdapterRegistry(noun="widget", adapters_module="app.ai.purposes")


def test_register_and_get_returns_instance() -> None:
    reg = _fresh()

    @reg.register("alpha")
    class Alpha(_Widget):
        def __init__(self, *, settings: object | None = None) -> None:
            self.settings = settings

        def run(self) -> str:
            return "alpha"

    got = reg.get("alpha")
    assert isinstance(got, Alpha)
    assert got.run() == "alpha"
    assert got.settings is None


def test_get_passes_settings_through() -> None:
    reg = _fresh()
    marker = object()

    @reg.register("beta")
    class Beta(_Widget):
        def __init__(self, *, settings: object | None = None) -> None:
            self.settings = settings

        def run(self) -> str:
            return "beta"

    assert reg.get("beta", settings=marker).settings is marker


def test_available_is_sorted() -> None:
    reg = _fresh()

    for key in ("zeta", "alpha", "mu"):

        @reg.register(key)
        class _W(_Widget):
            def run(self) -> str:
                return "w"

    assert reg.available() == ["alpha", "mu", "zeta"]


def test_duplicate_key_different_class_raises() -> None:
    reg = _fresh()

    @reg.register("dup")
    class One(_Widget):
        def run(self) -> str:
            return "1"

    with pytest.raises(ValueError, match="widget key 'dup' is already registered"):

        @reg.register("dup")
        class Two(_Widget):
            def run(self) -> str:
                return "2"


def test_re_registering_same_class_is_idempotent() -> None:
    reg = _fresh()

    class Same(_Widget):
        def run(self) -> str:
            return "same"

    reg.register("k")(Same)
    reg.register("k")(Same)  # no raise
    assert isinstance(reg.get("k"), Same)


def test_unknown_key_raises_keyerror_with_available() -> None:
    reg = _fresh()

    @reg.register("known")
    class Known(_Widget):
        def run(self) -> str:
            return "known"

    with pytest.raises(KeyError, match="No widget registered for 'missing'"):
        reg.get("missing")
