"""Backward-compatible re-exports for pipeline test helpers."""

from tests.worker.pipeline_helpers import (
    FailingScraper,
    FakeScraper,
    RecordingNotifier,
)
from tests.worker.pipeline_helpers import (
    aware as _aware,
)
from tests.worker.pipeline_helpers import (
    make_search as _make_search,
)
from tests.worker.pipeline_helpers import (
    make_user as _make_user,
)
from tests.worker.pipeline_helpers import (
    pipeline as _pipeline,
)
from tests.worker.pipeline_helpers import (
    posting as _posting,
)

__all__ = [
    "FakeScraper",
    "FailingScraper",
    "RecordingNotifier",
    "_aware",
    "_make_search",
    "_make_user",
    "_pipeline",
    "_posting",
]
