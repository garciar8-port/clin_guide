"""Tests for query tracing."""

from clinguide.core.tracing import new_trace


class TestTracing:
    def test_trace_creates_id(self):
        trace = new_trace("test query")
        assert trace.trace_id.startswith("t-")

    def test_span_recording(self):
        trace = new_trace("test query")
        trace.start_span("test_span", key="value")
        trace.end_span(result="ok")
        assert len(trace.spans) == 1
        assert trace.spans[0].name == "test_span"
        assert trace.spans[0].attributes["key"] == "value"
        assert trace.spans[0].attributes["result"] == "ok"
        assert trace.spans[0].latency_ms >= 0

    def test_to_dict(self):
        trace = new_trace("test query")
        trace.start_span("span1")
        trace.end_span()
        d = trace.to_dict()
        assert d["query"] == "test query"
        assert len(d["spans"]) == 1
        assert "total_latency_ms" in d
