from __future__ import annotations

from pathlib import Path

import yaml

from .models import Item


def save_item(item: Item, directory: Path) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{item.id}.yaml"
    path.write_text(yaml.dump(item.model_dump(mode="json"), allow_unicode=True, sort_keys=False), encoding="utf-8")
    return path


def load_item(path: Path) -> Item:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return Item.model_validate(data)


def load_all_items(directory: Path) -> list[Item]:
    return [load_item(p) for p in sorted(directory.glob("*.yaml"))]
