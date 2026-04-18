"""SQL queries and high-level data extraction from a TraceSession."""

from __future__ import annotations

from typing import Any

from tracelens.trace.processor import TraceSession

PROCESS_INVENTORY_SQL = "select pid, name from process where pid > 0 order by pid"
THREAD_INVENTORY_SQL = """
select t.tid, t.name as thread_name, p.pid, p.name as process_name
from thread t join process p using(upid)
where t.tid > 0
order by p.pid, t.tid
"""

SLICES_FOR_THREAD_SQL = """
select s.ts, s.dur, s.name, t.tid, t.name as thread_name
from slice s
join thread_track tt on s.track_id = tt.id
join thread t on tt.utid = t.utid
join process p on t.upid = p.upid
where p.pid = {pid}
order by s.ts
"""

THREAD_STATE_SQL = """
select ts.ts, ts.dur, ts.state, t.tid, t.name as thread_name
from thread_state ts
join thread t using(utid)
join process p on t.upid = p.upid
where p.pid = {pid} and ts.dur > 0
order by ts.ts
"""


def get_processes(session: TraceSession) -> list[dict[str, Any]]:
    return session.query(PROCESS_INVENTORY_SQL)


def get_threads(session: TraceSession) -> list[dict[str, Any]]:
    return session.query(THREAD_INVENTORY_SQL)


def get_threads_for_process(
    session: TraceSession, pid: int
) -> list[dict[str, Any]]:
    return session.query(
        f"select t.tid, t.name as thread_name from thread t "
        f"join process p using(upid) where p.pid = {pid} order by t.tid"
    )


def get_slices_for_process(
    session: TraceSession, pid: int
) -> list[dict[str, Any]]:
    return session.query(SLICES_FOR_THREAD_SQL.format(pid=pid))


def get_thread_states_for_process(
    session: TraceSession, pid: int
) -> list[dict[str, Any]]:
    return session.query(THREAD_STATE_SQL.format(pid=pid))
