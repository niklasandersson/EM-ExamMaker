from __future__ import annotations

import os
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from enum import auto, Enum
from pathlib import Path

import click

from .models import CourseAssignment, Criterion, Difficulty


ITEM_TEMPLATE = r"""\documentclass[12pt]{article}
\usepackage[a4paper, margin=2cm]{geometry}
\usepackage[utf8]{inputenc}
\usepackage{amsmath, amssymb}
\usepackage{parskip}

% Renders one grading criterion. Usage: \criterion{description}{points}
\newcommand{\criterion}[2]{\noindent\textbullet~#1\hfill\textit{(#2~pts)}\par\smallskip}

% Renders one course assignment. Usage: \course{code}{difficulty}{topic}
\newcommand{\course}[3]{\noindent\textbullet~\texttt{#1}\quad\textit{#2}~\textit{#3}\par\smallskip}

\begin{document}

\noindent\textbf{Question}
\medskip

% @@BEGIN_BODY
Write your question body here in \LaTeX{}.
% @@END_BODY

\bigskip\hrule\bigskip

\noindent\textbf{Solution}
\medskip

% @@BEGIN_SOLUTION
% Write the solution here in \LaTeX{}. Lines starting with % are ignored.
% @@END_SOLUTION

\bigskip\hrule\bigskip

\noindent\textbf{Grading Criteria}
\medskip

% @@BEGIN_CRITERIA
% Add criteria using \criterion{description}{points}:
% @@END_CRITERIA

\bigskip\hrule\bigskip

\noindent\textbf{Courses}
\medskip

% @@BEGIN_COURSES
% Add courses using \course{course\_code}{difficulty}{topic}:
% Difficulty: easy | medium | hard. Topic is optional (leave \{\} empty).
% @@END_COURSES

\end{document}
"""

_GUI_EDITORS = ("codium", "code", "code-insiders", "subl")

# Matches \criterion{description}{points} with optional surrounding whitespace
_CRITERION_RE = re.compile(r"^\s*\\criterion\{([^}]*)\}\{([^}]*)\}\s*$")

# Matches \course{code}{difficulty}{topic} with optional surrounding whitespace
_COURSE_RE = re.compile(r"^\s*\\course\{([^}]*)\}\{([^}]*)\}\{([^}]*)\}\s*$")


class TemplateParseError(ValueError):
    """Raised when the edited .tex file cannot be parsed into item fields."""


@dataclass
class ParsedTemplate:
    body: str
    criteria: list[Criterion] = field(default_factory=list)
    solution: str | None = None
    courses: dict[str, CourseAssignment] = field(default_factory=dict)


def find_editor() -> list[str]:
    """Return a command argv list for the best available editor.

    Detection order: codium → code → code-insiders → subl → $VISUAL → $EDITOR → vi.
    GUI editors get ``--wait`` appended so the subprocess blocks until the file is closed.
    """
    for name in _GUI_EDITORS:
        if shutil.which(name):
            return [name, "--new-window", "--wait"]

    for env_var in ("VISUAL", "EDITOR"):
        val = os.environ.get(env_var, "").strip()
        if val:
            parts = val.split()
            if shutil.which(parts[0]):
                return parts

    if shutil.which("vi"):
        return ["vi"]

    raise click.ClickException(
        "No editor found. Install VS Codium or VS Code, or set the EDITOR "
        "or VISUAL environment variable."
    )


def open_editor(path: Path) -> None:
    """Open *path* in the detected editor and block until the user closes it."""
    cmd = find_editor()
    cmd = cmd + [str(path)]
    try:
        subprocess.run(cmd, check=True, shell=True)
    except subprocess.CalledProcessError as exc:
        raise click.ClickException(f"Editor exited with code {exc.returncode}.")
    except FileNotFoundError:
        raise click.ClickException(f"Editor executable not found: {cmd[0]!r}")


class _Section(Enum):
    OUTSIDE = auto()
    IN_BODY = auto()
    IN_SOLUTION = auto()
    IN_CRITERIA = auto()
    IN_COURSES = auto()


def parse_template(content: str) -> ParsedTemplate:
    """Parse an edited .tex template into structured item fields.

    Uses a line-by-line state machine keyed on ``% @@BEGIN_X`` / ``% @@END_X``
    marker lines.
    """
    state = _Section.OUTSIDE
    body_lines: list[str] = []
    solution_lines: list[str] = []
    criteria_lines: list[str] = []
    courses_lines: list[str] = []

    for line in content.splitlines():
        stripped = line.strip()

        if stripped == "% @@BEGIN_BODY":
            state = _Section.IN_BODY
        elif stripped == "% @@END_BODY":
            state = _Section.OUTSIDE
        elif stripped == "% @@BEGIN_SOLUTION":
            state = _Section.IN_SOLUTION
        elif stripped == "% @@END_SOLUTION":
            state = _Section.OUTSIDE
        elif stripped == "% @@BEGIN_CRITERIA":
            state = _Section.IN_CRITERIA
        elif stripped == "% @@END_CRITERIA":
            state = _Section.OUTSIDE
        elif stripped == "% @@BEGIN_COURSES":
            state = _Section.IN_COURSES
        elif stripped == "% @@END_COURSES":
            state = _Section.OUTSIDE
        elif state == _Section.IN_BODY:
            body_lines.append(line)
        elif state == _Section.IN_SOLUTION:
            if stripped and not stripped.startswith("%"):
                solution_lines.append(stripped)
        elif state == _Section.IN_CRITERIA:
            if stripped and not stripped.startswith("%"):
                criteria_lines.append(stripped)
        elif state == _Section.IN_COURSES:
            if stripped and not stripped.startswith("%"):
                courses_lines.append(stripped)

    body = "\n".join(body_lines).strip()
    if not body:
        raise TemplateParseError(
            "Body section is empty — please write the question text between the BODY markers."
        )

    solution_text = "\n".join(solution_lines).strip() or None

    criteria: list[Criterion] = []
    for raw in criteria_lines:
        m = _CRITERION_RE.match(raw)
        if not m:
            raise TemplateParseError(
                f"Bad criterion line: {raw!r} — "
                r"expected format: \criterion{description}{points}"
            )
        desc = m.group(1).strip()
        pts_str = m.group(2).strip()
        try:
            pts = int(pts_str)
        except ValueError:
            raise TemplateParseError(
                f"Criterion points must be an integer, got: {pts_str!r}"
            )
        criteria.append(Criterion(description=desc, points=pts))

    _valid_difficulties = {d.value for d in Difficulty}
    courses: dict[str, Difficulty] = {}
    for raw in courses_lines:
        m = _COURSE_RE.match(raw)
        if not m:
            raise TemplateParseError(
                f"Bad course line: {raw!r} — "
                r"expected format: \course{course_code}{difficulty}"
            )
        code = m.group(1).strip()
        diff_str = m.group(2).strip().lower()
        topic_str = m.group(3).strip() or None
        if diff_str not in _valid_difficulties:
            raise TemplateParseError(
                f"Invalid difficulty {diff_str!r} for course {code!r} — "
                f"must be one of: {', '.join(sorted(_valid_difficulties))}"
            )
        courses[code] = CourseAssignment(difficulty=Difficulty(diff_str), topic=topic_str)

    return ParsedTemplate(body=body, criteria=criteria, solution=solution_text, courses=courses)
