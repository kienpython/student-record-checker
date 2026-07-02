"""Run-scoped memory used by the agent."""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Memory:
    """Tracks processed records and compact per-record results for one run."""

    processed_ids: set[str] = field(default_factory=set)
    results: dict[str, dict[str, Any]] = field(default_factory=dict)

    def contains(self, record_id: str) -> bool:
        return record_id in self.processed_ids

    def remember(self, record_id: str, **result: Any) -> None:
        self.processed_ids.add(record_id)
        self.results[record_id] = result

    def count(self) -> int:
        return len(self.processed_ids)
