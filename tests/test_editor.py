import os

import pytest
import click

from exammaker.editor import (
    ITEM_TEMPLATE,
    ParsedTemplate,
    TemplateParseError,
    find_editor,
    parse_template,
)
from exammaker.models import CourseAssignment, Criterion, Difficulty


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_template(
    body: str = "Solve $x^2 = 4$.",
    solution: str = "",
    criteria: str = "",
    courses: str = "",
) -> str:
    """Return a .tex template string with the given section contents."""
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


# ---------------------------------------------------------------------------
# parse_template – body
# ---------------------------------------------------------------------------

class TestParseTemplateBody:
    def test_extracts_body(self):
        result = parse_template(_build_template(body="What is $E = mc^2$?"))
        assert result.body == "What is $E = mc^2$?"

    def test_strips_body_whitespace(self):
        result = parse_template(_build_template(body="\n  Trimmed body.  \n"))
        assert result.body == "Trimmed body."

    def test_multiline_body_preserved(self):
        body = "Line one.\n\nLine two."
        result = parse_template(_build_template(body=body))
        assert "Line one." in result.body
        assert "Line two." in result.body

    def test_empty_body_raises(self):
        content = _build_template(body="")
        with pytest.raises(TemplateParseError, match="empty"):
            parse_template(content)

    def test_whitespace_only_body_raises(self):
        content = _build_template(body="   \n\t  ")
        with pytest.raises(TemplateParseError, match="empty"):
            parse_template(content)

    def test_default_template_body_non_empty(self):
        # The unmodified ITEM_TEMPLATE has a placeholder body — should parse OK
        result = parse_template(ITEM_TEMPLATE)
        assert result.body  # placeholder text is non-empty


# ---------------------------------------------------------------------------
# parse_template – solution
# ---------------------------------------------------------------------------

class TestParseTemplateSolution:
    def test_solution_captured(self):
        result = parse_template(_build_template(solution="Dynamic programming decomposes..."))
        assert result.solution == "Dynamic programming decomposes..."

    def test_blank_solution_returns_none(self):
        result = parse_template(_build_template(solution=""))
        assert result.solution is None

    def test_comment_only_solution_returns_none(self):
        result = parse_template(_build_template(solution="% This is a comment\n% Another"))
        assert result.solution is None

    def test_multiline_solution(self):
        result = parse_template(_build_template(solution="Part one.\nPart two."))
        assert "Part one." in result.solution
        assert "Part two." in result.solution


# ---------------------------------------------------------------------------
# parse_template – criteria
# ---------------------------------------------------------------------------

class TestParseTemplateCriteria:
    def test_single_criterion(self):
        result = parse_template(_build_template(criteria=r"\criterion{Correct answer}{4}"))
        assert len(result.criteria) == 1
        assert result.criteria[0] == Criterion(description="Correct answer", points=4)

    def test_multiple_criteria(self):
        criteria = "\\criterion{Defines DP}{4}\n\\criterion{Gives example}{6}"
        result = parse_template(_build_template(criteria=criteria))
        assert len(result.criteria) == 2
        assert result.criteria[0].points == 4
        assert result.criteria[1].points == 6

    def test_comment_lines_ignored(self):
        criteria = "% This is a comment\n\\criterion{Actual criterion}{2}"
        result = parse_template(_build_template(criteria=criteria))
        assert len(result.criteria) == 1

    def test_blank_lines_ignored(self):
        criteria = "\n\\criterion{Actual criterion}{2}\n\n"
        result = parse_template(_build_template(criteria=criteria))
        assert len(result.criteria) == 1

    def test_empty_criteria_returns_empty_list(self):
        result = parse_template(_build_template(criteria=""))
        assert result.criteria == []

    def test_invalid_format_raises(self):
        content = _build_template(criteria="No backslash criterion here")
        with pytest.raises(TemplateParseError, match="Bad criterion"):
            parse_template(content)

    def test_non_integer_points_raises(self):
        content = _build_template(criteria=r"\criterion{Good answer}{four}")
        with pytest.raises(TemplateParseError, match="integer"):
            parse_template(content)

    def test_whitespace_in_braces_stripped(self):
        result = parse_template(_build_template(criteria=r"\criterion{  Good answer  }{  3  }"))
        assert result.criteria[0].description == "Good answer"
        assert result.criteria[0].points == 3

    def test_pipe_in_description_supported(self):
        # | in description is fine since {} delimiters are used
        result = parse_template(_build_template(criteria=r"\criterion{$P(A | B)$}{5}"))
        assert result.criteria[0].description == "$P(A | B)$"
        assert result.criteria[0].points == 5


# ---------------------------------------------------------------------------
# parse_template – courses
# ---------------------------------------------------------------------------

class TestParseTemplateCourses:
    def test_single_course(self):
        result = parse_template(_build_template(courses=r"\course{CS101}{easy}{Intro}"))
        assert result.courses["CS101"].difficulty.value == "easy"
        assert result.courses["CS101"].topic == "Intro"

    def test_multiple_courses(self):
        result = parse_template(_build_template(courses="\\course{CS101}{easy}{Topic A}\n\\course{PHY200}{hard}{Topic B}"))
        assert result.courses["CS101"].difficulty.value == "easy"
        assert result.courses["PHY200"].difficulty.value == "hard"

    def test_empty_courses_returns_empty_dict(self):
        result = parse_template(_build_template(courses=""))
        assert result.courses == {}

    def test_comment_lines_ignored(self):
        result = parse_template(_build_template(courses="% A comment\n\\course{CS101}{medium}{Recursion}"))
        assert result.courses["CS101"].difficulty.value == "medium"

    def test_blank_lines_ignored(self):
        result = parse_template(_build_template(courses="\n\\course{CS101}{hard}{Sorting}\n\n"))
        assert result.courses["CS101"].difficulty.value == "hard"

    def test_all_difficulties_accepted(self):
        courses = "\\course{A}{easy}{}\n\\course{B}{medium}{}\n\\course{C}{hard}{}"
        result = parse_template(_build_template(courses=courses))
        assert result.courses["A"].difficulty.value == "easy"
        assert result.courses["B"].difficulty.value == "medium"
        assert result.courses["C"].difficulty.value == "hard"

    def test_difficulty_case_insensitive(self):
        result = parse_template(_build_template(courses=r"\course{CS101}{EASY}{}"))
        assert result.courses["CS101"].difficulty == Difficulty.EASY

    def test_whitespace_in_braces_stripped(self):
        result = parse_template(_build_template(courses=r"\course{  CS101  }{  medium  }{  Graphs  }"))
        assert "CS101" in result.courses
        assert result.courses["CS101"].difficulty.value == "medium"

    def test_topic_saved(self):
        result = parse_template(_build_template(courses=r"\course{CS101}{easy}{Graph Theory}"))
        assert result.courses["CS101"].topic == "Graph Theory"

    def test_blank_topic_stored_as_none(self):
        result = parse_template(_build_template(courses=r"\course{CS101}{easy}{}"))
        assert result.courses["CS101"].topic is None

    def test_topic_whitespace_stripped(self):
        result = parse_template(_build_template(courses=r"\course{CS101}{easy}{  Week 3  }"))
        assert result.courses["CS101"].topic == "Week 3"

    def test_invalid_format_raises(self):
        content = _build_template(courses="CS101 easy")
        with pytest.raises(TemplateParseError, match="Bad course"):
            parse_template(content)

    def test_missing_topic_arg_raises(self):
        # Two-arg form no longer valid — must include topic braces
        content = _build_template(courses=r"\course{CS101}{easy}")
        with pytest.raises(TemplateParseError, match="Bad course"):
            parse_template(content)

    def test_invalid_difficulty_raises(self):
        content = _build_template(courses=r"\course{CS101}{impossible}{}")
        with pytest.raises(TemplateParseError, match="Invalid difficulty"):
            parse_template(content)


# ---------------------------------------------------------------------------
# find_editor
# ---------------------------------------------------------------------------

class TestFindEditor:
    def test_gui_editor_gets_wait_flag(self, monkeypatch):
        monkeypatch.setattr("shutil.which", lambda name: "/usr/bin/codium" if name == "codium" else None)
        assert find_editor() == ["codium", "--new-window", "--wait"]

    def test_code_gets_wait_flag(self, monkeypatch):
        def which(name):
            return "/usr/bin/code" if name == "code" else None
        monkeypatch.setattr("shutil.which", which)
        assert find_editor() == ["code", "--new-window", "--wait"]

    def test_visual_env_used_as_fallback(self, monkeypatch):
        monkeypatch.setattr("shutil.which", lambda name: "/usr/bin/nano" if name == "nano" else None)
        monkeypatch.setenv("VISUAL", "nano")
        monkeypatch.delenv("EDITOR", raising=False)
        result = find_editor()
        assert result == ["nano"]

    def test_editor_env_used_when_visual_missing(self, monkeypatch):
        monkeypatch.setattr("shutil.which", lambda name: "/usr/bin/vim" if name == "vim" else None)
        monkeypatch.delenv("VISUAL", raising=False)
        monkeypatch.setenv("EDITOR", "vim")
        result = find_editor()
        assert result == ["vim"]

    def test_multi_word_editor_split(self, monkeypatch):
        monkeypatch.setattr("shutil.which", lambda name: "/usr/bin/emacsclient" if name == "emacsclient" else None)
        monkeypatch.setenv("EDITOR", "emacsclient -t")
        monkeypatch.delenv("VISUAL", raising=False)
        result = find_editor()
        assert result == ["emacsclient", "-t"]

    def test_raises_when_nothing_found(self, monkeypatch):
        monkeypatch.setattr("shutil.which", lambda name: None)
        monkeypatch.delenv("VISUAL", raising=False)
        monkeypatch.delenv("EDITOR", raising=False)
        with pytest.raises(click.ClickException):
            find_editor()

    def test_gui_editors_checked_before_env(self, monkeypatch):
        # Both codium and EDITOR present — codium wins
        monkeypatch.setattr("shutil.which", lambda name: "/usr/bin/codium" if name == "codium" else "/usr/bin/vim")
        monkeypatch.setenv("EDITOR", "vim")
        result = find_editor()
        assert result == ["codium", "--new-window", "--wait"]
