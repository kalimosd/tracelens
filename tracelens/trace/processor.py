from __future__ import annotations

import re
import socket
from dataclasses import dataclass, field
from typing import Any

import perfetto.trace_processor.api as _tp_api
from perfetto.trace_processor import TraceProcessor as _TP
from perfetto.trace_processor import TraceProcessorConfig
from perfetto.trace_processor.platform import PlatformDelegate


class TraceQueryError(ValueError):
    pass


@dataclass(slots=True)
class QueryGuard:
    max_rows: int
    allowed_tables: set[str]

    def validate(self, sql: str) -> None:
        normalized = sql.strip().lower()
        if normalized.count(";") > 1 or (";" in normalized and not normalized.endswith(";")):
            raise TraceQueryError("multiple statements are not allowed")

        tables = set(re.findall(r"from\s+([a-zA-Z_][a-zA-Z0-9_]*)", normalized))
        tables.update(re.findall(r"join\s+([a-zA-Z_][a-zA-Z0-9_]*)", normalized))
        disallowed = tables - self.allowed_tables
        if disallowed:
            raise TraceQueryError(f"disallowed table: {sorted(disallowed)[0]}")


class _IPv4PlatformDelegate(PlatformDelegate):
    """Force 127.0.0.1 to avoid macOS IPv6 resolution issues."""

    def get_bind_addr(self, port: int) -> tuple[str, int]:
        if port:
            return "127.0.0.1", port
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.bind(("", 0))
        sock.listen(5)
        port = sock.getsockname()[1]
        sock.close()
        return "127.0.0.1", port


# Patch the module-level delegate so all TraceProcessor instances use IPv4
_tp_api.PLATFORM_DELEGATE = _IPv4PlatformDelegate

ALLOWED_TABLES = {
    "process", "thread", "slice", "thread_state", "sched_slice",
    "thread_track", "process_track", "counter", "counter_track",
    "args", "ftrace_event", "raw", "actual_frame_timeline_slice",
    "expected_frame_timeline_slice",
}


@dataclass
class TraceSession:
    _tp: _TP
    guard: QueryGuard = field(init=False)

    def __post_init__(self) -> None:
        self.guard = QueryGuard(max_rows=50_000, allowed_tables=ALLOWED_TABLES)

    def query(self, sql: str) -> list[dict[str, Any]]:
        self.guard.validate(sql)
        result = self._tp.query(sql)
        rows: list[dict[str, Any]] = []
        for row in result:
            rows.append(dict(row.__dict__))
            if len(rows) >= self.guard.max_rows:
                break
        return rows

    def close(self) -> None:
        self._tp.close()

    def __enter__(self) -> TraceSession:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()


def load_trace(path: str) -> TraceSession:
    config = TraceProcessorConfig(load_timeout=30)
    tp = _TP(trace=path, config=config)
    return TraceSession(_tp=tp)
