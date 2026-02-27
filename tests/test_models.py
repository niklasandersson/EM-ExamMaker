import pytest
from pydantic import ValidationError

from exammaker.models import CourseAssignment, Criterion, Difficulty, Item


def make_item(**overrides) -> Item:
    defaults = dict(
        body=r"Explain \textbf{dynamic programming}.",
        points=10,
        courses={
            "CS201": CourseAssignment(difficulty=Difficulty.MEDIUM, topic="Dynamic Programming"),
            "CS301": CourseAssignment(difficulty=Difficulty.EASY, topic="Intro"),
        },
        criteria=[
            Criterion(description="Correctly defines DP", points=4),
            Criterion(description="Provides a valid example", points=6),
        ],
    )
    defaults.update(overrides)
    return Item(**defaults)


class TestItem:
    def test_id_auto_generated(self):
        item = make_item()
        assert isinstance(item.id, str)
        assert len(item.id) == 8

    def test_different_difficulties_per_course(self):
        item = make_item()
        assert item.courses["CS201"].difficulty == Difficulty.MEDIUM
        assert item.courses["CS301"].difficulty == Difficulty.EASY

    def test_criteria_points_are_int(self):
        item = make_item()
        for c in item.criteria:
            assert isinstance(c.points, int)

    def test_solution_defaults_to_none(self):
        item = make_item()
        assert item.solution is None

    def test_invalid_difficulty_rejected(self):
        with pytest.raises(ValidationError):
            make_item(courses={"CS201": CourseAssignment(difficulty="impossible")})


class TestRoundTrip:
    def test_yaml_round_trip(self, tmp_path):
        from exammaker.storage import load_item, save_item

        item = make_item()
        path = save_item(item, tmp_path)
        loaded = load_item(path)
        assert loaded == item

    def test_all_items_loaded(self, tmp_path):
        from exammaker.storage import load_all_items, save_item

        items = [make_item() for _ in range(3)]
        for item in items:
            save_item(item, tmp_path)

        loaded = load_all_items(tmp_path)
        assert len(loaded) == 3
        assert {i.id for i in loaded} == {i.id for i in items}
