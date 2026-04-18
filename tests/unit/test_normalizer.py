from tracelens.trace.normalizer import normalize_rows


def test_normalize_rows_maps_columns_to_dicts():
    rows = [("main", 42), ("RenderThread", 9)]
    columns = ["thread_name", "dur_ms"]

    result = normalize_rows(columns, rows)

    assert result == [
        {"thread_name": "main", "dur_ms": 42},
        {"thread_name": "RenderThread", "dur_ms": 9},
    ]
