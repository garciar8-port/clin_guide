"""Structured query tracing — logs each pipeline stage with latency and scores."""

import logging
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime

logger = logging.getLogger("clinguide.trace")


@dataclass
class SpanRecord:
    name: str
    start: float = 0.0
    end: float = 0.0
    attributes: dict = field(default_factory=dict)

    @property
    def latency_ms(self) -> float:
        return (self.end - self.start) * 1000


@dataclass
class QueryTrace:
    """Accumulates spans for a single query through the pipeline."""

    query: str
    trace_id: str = ""
    created_at: str = ""
    spans: list[SpanRecord] = field(default_factory=list)
    _current_span: SpanRecord | None = field(default=None, repr=False)

    def __post_init__(self) -> None:
        if not self.trace_id:
            self.trace_id = f"t-{int(time.time() * 1000)}"
        if not self.created_at:
            self.created_at = datetime.now(UTC).isoformat()

    def start_span(self, name: str, **attributes) -> None:
        self._current_span = SpanRecord(
            name=name, start=time.perf_counter(), attributes=attributes
        )

    def end_span(self, **attributes) -> None:
        if self._current_span:
            self._current_span.end = time.perf_counter()
            self._current_span.attributes.update(attributes)
            self.spans.append(self._current_span)
            logger.info(
                "span=%s latency_ms=%.1f %s",
                self._current_span.name,
                self._current_span.latency_ms,
                " ".join(f"{k}={v}" for k, v in self._current_span.attributes.items()),
            )
            self._current_span = None

    def to_dict(self) -> dict:
        return {
            "trace_id": self.trace_id,
            "query": self.query,
            "created_at": self.created_at,
            "total_latency_ms": sum(s.latency_ms for s in self.spans),
            "spans": [
                {
                    "name": s.name,
                    "latency_ms": round(s.latency_ms, 1),
                    "attributes": s.attributes,
                }
                for s in self.spans
            ],
        }


def new_trace(query: str) -> QueryTrace:
    return QueryTrace(query=query)
