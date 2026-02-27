from click.testing import CliRunner
from exammaker.cli import main


def test_cli_help():
    runner = CliRunner()
    result = runner.invoke(main, ["--help"])
    assert result.exit_code == 0
    assert "ExamMaker" in result.output
