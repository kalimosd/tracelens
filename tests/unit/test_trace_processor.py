import pytest

from tracelens.trace.processor import QueryGuard, TraceQueryError


def test_query_guard_rejects_multiple_statements():
    guard = QueryGuard(max_rows=100, allowed_tables={"process"})

    with pytest.raises(TraceQueryError, match="multiple statements"):
        guard.validate("select * from process; select * from process")


def test_query_guard_rejects_disallowed_table():
    guard = QueryGuard(max_rows=100, allowed_tables={"process"})

    with pytest.raises(TraceQueryError, match="disallowed table"):
        guard.validate("select * from slice")
