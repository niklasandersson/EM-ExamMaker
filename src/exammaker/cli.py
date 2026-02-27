import tempfile
from pathlib import Path

import click

from .editor import ITEM_TEMPLATE, TemplateParseError, open_editor, parse_template
from .models import Item
from .storage import save_item


@click.group()
def main():
    """EM – ExamMaker CLI."""
    pass


@main.group()
def item():
    """Manage exam items."""
    pass


@item.command("add")
@click.option(
    "--items-dir",
    default="items",
    show_default=True,
    help="Directory to store item YAML files.",
    type=click.Path(),
)
def item_add(items_dir: str) -> None:
    """Create a new exam item interactively."""
    with tempfile.NamedTemporaryFile(
        suffix=".tex", mode="w", encoding="utf-8", delete=False
    ) as tmp:
        tmp.write(ITEM_TEMPLATE)
        tmp_path = Path(tmp.name)

    try:
        open_editor(tmp_path)
        content = tmp_path.read_text(encoding="utf-8")
        try:
            parsed = parse_template(content)
        except TemplateParseError as exc:
            raise click.ClickException(str(exc))
    finally:
        tmp_path.unlink(missing_ok=True)

    points = sum(c.points for c in parsed.criteria)
    new_item = Item(
        body=parsed.body,
        points=points,
        courses=parsed.courses,
        criteria=parsed.criteria,
        solution=parsed.solution,
    )
    out_path = save_item(new_item, Path(items_dir))
    click.echo(f"Saved: {out_path}")
