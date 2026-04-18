from typer.testing import CliRunner

from tracelens.main import app


runner = CliRunner()


def test_cli_analyze_outputs_minimal_analysis_result():
    result = runner.invoke(
        app,
        [
            "analyze",
            "--scenario",
            "switching mode stutters",
            "--process",
            "com.example.app",
        ],
    )

    assert result.exit_code == 0
    assert "initial analysis ready" in result.stdout
    assert "Top abnormal window" in result.stdout
    assert "Selected role-first strategy" in result.stdout
