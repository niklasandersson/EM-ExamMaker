from pathlib import Path
from unittest.mock import patch

import yaml
from click.testing import CliRunner

from exammaker.cli import main
from exammaker.editor import ITEM_TEMPLATE


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_tex(
    body: str = r"Solve $x^2 = 4$.",
    solution: str = "",
    criteria: str = "",
    courses: str = "",
) -> str:
    """Return a .tex string that simulates what the user saves in the editor."""
    return (
        "\\begin{document}\n\n"
        "% @@BEGIN_BODY\n"
        f"{body}\n"
        "% @@END_BODY\n\n"
        "\\end{document}\n\n"
        "% @@BEGIN_SOLUTION\n"
        f"{solution}\n"
        "% @@END_SOLUTION\n\n"
        "% @@BEGIN_CRITERIA\n"
        f"{criteria}\n"
        "% @@END_CRITERIA\n\n"
        "% @@BEGIN_COURSES\n"
        f"{courses}\n"
        "% @@END_COURSES\n"
    )


def _fake_editor(content: str):
    """Return a replacement for open_editor that writes *content* to the temp path."""
    def _write(path: Path) -> None:
        path.write_text(content, encoding="utf-8")
    return _write


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestItemAdd:
    def test_help_shows_items_dir_option(self):
        runner = CliRunner()
        result = runner.invoke(main, ["item", "add", "--help"])
        assert result.exit_code == 0
        assert "--items-dir" in result.output

    def test_happy_path_saves_yaml(self, tmp_path):
        runner = CliRunner()
        tex = _make_tex(body=r"What is \textbf{dynamic programming}?")
        with patch("exammaker.cli.open_editor", _fake_editor(tex)):
            result = runner.invoke(
                main,
                ["item", "add", "--items-dir", str(tmp_path)],
            )
        assert result.exit_code == 0, result.output
        assert "Saved:" in result.output
        yamls = list(tmp_path.glob("*.yaml"))
        assert len(yamls) == 1

    def test_points_calculated_from_criteria(self, tmp_path):
        runner = CliRunner()
        tex = _make_tex(body="A question.", criteria="\\criterion{Part one}{4}\n\\criterion{Part two}{6}")
        with patch("exammaker.cli.open_editor", _fake_editor(tex)):
            runner.invoke(main, ["item", "add", "--items-dir", str(tmp_path)])
        data = yaml.safe_load(next(tmp_path.glob("*.yaml")).read_text(encoding="utf-8"))
        assert data["points"] == 10  # 4 + 6

    def test_points_zero_when_no_criteria(self, tmp_path):
        runner = CliRunner()
        tex = _make_tex(body="A question.")
        with patch("exammaker.cli.open_editor", _fake_editor(tex)):
            runner.invoke(main, ["item", "add", "--items-dir", str(tmp_path)])
        data = yaml.safe_load(next(tmp_path.glob("*.yaml")).read_text(encoding="utf-8"))
        assert data["points"] == 0

    def test_saved_yaml_has_correct_body(self, tmp_path):
        runner = CliRunner()
        body = r"Explain \textbf{recursion}."
        tex = _make_tex(body=body)
        with patch("exammaker.cli.open_editor", _fake_editor(tex)):
            runner.invoke(main, ["item", "add", "--items-dir", str(tmp_path)])
        data = yaml.safe_load(next(tmp_path.glob("*.yaml")).read_text(encoding="utf-8"))
        assert data["body"] == body

    def test_courses_from_template_saved(self, tmp_path):
        runner = CliRunner()
        tex = _make_tex(body="A question.", courses="\\course{CS101}{easy}{Topic A}\n\\course{PHY200}{hard}{Topic B}")
        with patch("exammaker.cli.open_editor", _fake_editor(tex)):
            result = runner.invoke(main, ["item", "add", "--items-dir", str(tmp_path)])
        assert result.exit_code == 0, result.output
        data = yaml.safe_load(next(tmp_path.glob("*.yaml")).read_text(encoding="utf-8"))
        assert data["courses"]["CS101"] == {"difficulty": "easy", "topic": "Topic A"}
        assert data["courses"]["PHY200"] == {"difficulty": "hard", "topic": "Topic B"}

    def test_criteria_saved(self, tmp_path):
        runner = CliRunner()
        tex = _make_tex(
            body="A question.",
            criteria="\\criterion{Correct definition}{4}\n\\criterion{Good example}{6}",
        )
        with patch("exammaker.cli.open_editor", _fake_editor(tex)):
            runner.invoke(main, ["item", "add", "--items-dir", str(tmp_path)])
        data = yaml.safe_load(next(tmp_path.glob("*.yaml")).read_text(encoding="utf-8"))
        assert len(data["criteria"]) == 2
        assert data["criteria"][0] == {"description": "Correct definition", "points": 4}

    def test_solution_saved(self, tmp_path):
        runner = CliRunner()
        tex = _make_tex(body="A question.", solution="The answer is 42.")
        with patch("exammaker.cli.open_editor", _fake_editor(tex)):
            runner.invoke(main, ["item", "add", "--items-dir", str(tmp_path)])
        data = yaml.safe_load(next(tmp_path.glob("*.yaml")).read_text(encoding="utf-8"))
        assert data["solution"] == "The answer is 42."

    def test_blank_solution_not_stored(self, tmp_path):
        runner = CliRunner()
        tex = _make_tex(body="A question.", solution="")
        with patch("exammaker.cli.open_editor", _fake_editor(tex)):
            runner.invoke(main, ["item", "add", "--items-dir", str(tmp_path)])
        data = yaml.safe_load(next(tmp_path.glob("*.yaml")).read_text(encoding="utf-8"))
        assert data["solution"] is None

    def test_empty_body_shows_error(self, tmp_path):
        runner = CliRunner()
        tex = _make_tex(body="")
        with patch("exammaker.cli.open_editor", _fake_editor(tex)):
            result = runner.invoke(main, ["item", "add", "--items-dir", str(tmp_path)])
        assert result.exit_code != 0
        assert "empty" in result.output.lower()
        assert list(tmp_path.glob("*.yaml")) == []

    def test_malformed_criteria_shows_error(self, tmp_path):
        runner = CliRunner()
        tex = _make_tex(body="A question.", criteria="No backslash criterion here")
        with patch("exammaker.cli.open_editor", _fake_editor(tex)):
            result = runner.invoke(main, ["item", "add", "--items-dir", str(tmp_path)])
        assert result.exit_code != 0
        assert "Bad criterion" in result.output

    def test_invalid_difficulty_shows_error(self, tmp_path):
        runner = CliRunner()
        tex = _make_tex(body="A question.", courses=r"\course{CS101}{impossible}{}")
        with patch("exammaker.cli.open_editor", _fake_editor(tex)):
            result = runner.invoke(main, ["item", "add", "--items-dir", str(tmp_path)])
        assert result.exit_code != 0
        assert "Invalid difficulty" in result.output

    def test_items_dir_created_if_missing(self, tmp_path):
        new_dir = tmp_path / "subdir" / "items"
        assert not new_dir.exists()
        runner = CliRunner()
        tex = _make_tex(body="A question.")
        with patch("exammaker.cli.open_editor", _fake_editor(tex)):
            result = runner.invoke(main, ["item", "add", "--items-dir", str(new_dir)])
        assert result.exit_code == 0, result.output
        assert new_dir.exists()
        assert len(list(new_dir.glob("*.yaml"))) == 1

    def test_no_courses_saved_as_empty_dict(self, tmp_path):
        runner = CliRunner()
        tex = _make_tex(body="A question.")
        with patch("exammaker.cli.open_editor", _fake_editor(tex)):
            runner.invoke(main, ["item", "add", "--items-dir", str(tmp_path)])
        data = yaml.safe_load(next(tmp_path.glob("*.yaml")).read_text(encoding="utf-8"))
        assert data["courses"] == {}
