from tracelens.skills.long_task_detection import LongTaskDetectionSkill


def test_detects_long_slices():
    slices = [
        {"name": "short", "dur": 5_000_000},
        {"name": "long", "dur": 50_000_000},
        {"name": "medium", "dur": 20_000_000},
    ]
    result = LongTaskDetectionSkill().run(slices)
    assert len(result) == 2
    assert result[0]["name"] == "long"
    assert result[1]["name"] == "medium"


def test_empty_when_no_long_slices():
    slices = [{"name": "fast", "dur": 1_000_000}]
    assert LongTaskDetectionSkill().run(slices) == []


def test_custom_threshold():
    slices = [{"name": "a", "dur": 10_000_000}]
    assert len(LongTaskDetectionSkill(threshold_ns=5_000_000).run(slices)) == 1
    assert len(LongTaskDetectionSkill(threshold_ns=15_000_000).run(slices)) == 0
