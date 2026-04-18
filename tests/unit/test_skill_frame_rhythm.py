from tracelens.skills.frame_rhythm import FrameRhythmSkill


def test_detects_jank_frames():
    slices = [
        {"name": "DrawFrame", "ts": 0, "dur": 10_000_000},
        {"name": "DrawFrame", "ts": 16_000_000, "dur": 10_000_000},  # normal
        {"name": "DrawFrame", "ts": 66_000_000, "dur": 10_000_000},  # 50ms gap = jank
    ]
    result = FrameRhythmSkill().run(slices)
    assert result["frame_count"] == 3
    assert result["jank_count"] == 1
    assert result["janks"][0]["interval_ms"] == 50


def test_no_jank_when_smooth():
    slices = [
        {"name": "DrawFrame", "ts": 0, "dur": 5_000_000},
        {"name": "DrawFrame", "ts": 16_000_000, "dur": 5_000_000},
        {"name": "DrawFrame", "ts": 32_000_000, "dur": 5_000_000},
    ]
    result = FrameRhythmSkill().run(slices)
    assert result["jank_count"] == 0


def test_too_few_frames():
    result = FrameRhythmSkill().run([{"name": "DrawFrame", "ts": 0, "dur": 5_000_000}])
    assert result["frame_count"] == 1
    assert result["janks"] == []


def test_ignores_non_frame_slices():
    slices = [
        {"name": "inflate", "ts": 0, "dur": 50_000_000},
        {"name": "DrawFrame", "ts": 100_000_000, "dur": 5_000_000},
    ]
    result = FrameRhythmSkill().run(slices)
    assert result["frame_count"] == 1
