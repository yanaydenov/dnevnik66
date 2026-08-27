import pytest
import rich_formatters as rf


def test_rich_schedule():
    lessons = [
        {"num": 1, "name": "Алгебра", "room": "204", "beginHour": 8, "beginMinute": 30, "endHour": 9, "endMinute": 10}
    ]
    blocks = rf.rich_schedule(0, lessons)
    assert any(b.get("type") == "heading" for b in blocks)
    assert any(b.get("type") == "table" for b in blocks)


def test_rich_homework():
    hw = {
        "date": "2025-09-01",
        "homework": [
            {"lessonName": "Русский язык", "description": "Упр. 45", "filesCount": 1}
        ]
    }
    blocks = rf.rich_homework(hw)
    assert any(b.get("type") == "heading" for b in blocks)
    details_blocks = [b for b in blocks if b.get("type") == "details"]
    assert len(details_blocks) == 1
    assert "Русский язык" in details_blocks[0].get("summary", "")


def test_rich_period_grades():
    disciplines = [
        {"name": "Алгебра", "grades": ["5", "4"], "average": 4.5, "averagew": 4.6}
    ]
    blocks = rf.rich_period_grades(1, disciplines)
    assert any(b.get("type") == "heading" for b in blocks)
    assert any(b.get("type") == "table" for b in blocks)


def test_rich_year_grades():
    year_grades = [
        {"name": "Алгебра", "grades": ["5", "4", "5", "5"], "yeargrade": "5"}
    ]
    blocks = rf.rich_year_grades(year_grades)
    assert any(b.get("type") == "heading" for b in blocks)
    assert any(b.get("type") == "table" for b in blocks)


def test_rich_calls():
    blocks = rf.rich_calls()
    assert any(b.get("type") == "heading" for b in blocks)
    assert any(b.get("type") == "table" for b in blocks)


def test_rich_help():
    blocks = rf.rich_help()
    assert any(b.get("type") == "heading" for b in blocks)
    assert any(b.get("type") == "divider" for b in blocks)
