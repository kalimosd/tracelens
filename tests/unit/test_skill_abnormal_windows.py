from tracelens.skills.abnormal_windows import AbnormalWindowsSkill


def test_abnormal_windows_skill_ranks_candidate_windows():
    skill = AbnormalWindowsSkill()

    ranked = skill.run(
        [
            {"start": 0, "end": 10, "long_tasks": 0, "blocked_threads": 0, "scheduler_delay_ms": 1},
            {"start": 10, "end": 20, "long_tasks": 2, "blocked_threads": 1, "scheduler_delay_ms": 4},
        ]
    )

    assert ranked[0]["start"] == 10
    assert ranked[0]["score"] > ranked[1]["score"]
