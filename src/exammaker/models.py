from __future__ import annotations

from enum import Enum
import uuid

from pydantic import BaseModel, Field


class Difficulty(str, Enum):
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


class Criterion(BaseModel):
    description: str
    points: int


class Item(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:8])
    body: str
    points: int
    courses: dict[str, Difficulty] = Field(default_factory=dict)
    criteria: list[Criterion] = Field(default_factory=list)
    solution: str | None = None
