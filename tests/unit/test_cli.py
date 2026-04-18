from typer.testing import CliRunner

from tracelens.main import app


runner = CliRunner()


def test_cli_shows_trace_lens_name_in_help():
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "TraceLens" in result.stdout
    assert "analyze" in result.stdout
