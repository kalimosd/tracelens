from dataclasses import dataclass
from uuid import uuid4

from tracelens.types import AnalysisResult


@dataclass(slots=True)
class InMemoryArtifactStore:
    _items: dict[str, AnalysisResult] | None = None

    def __post_init__(self) -> None:
        if self._items is None:
            self._items = {}

    def save(self, result: AnalysisResult) -> str:
        session_id = str(uuid4())
        self._items[session_id] = result
        return session_id

    def load(self, session_id: str) -> AnalysisResult | None:
        return self._items.get(session_id)
