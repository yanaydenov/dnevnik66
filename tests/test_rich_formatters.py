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
    # Quarter test
    blocks_q = rf.rich_period_grades(1, disciplines, is_semester=False)
    assert any(b.get("type") == "heading" and "четверть" in b.get("text", "") for b in blocks_q)
    assert any(b.get("type") == "table" for b in blocks_q)

    # Semester test
    blocks_s = rf.rich_period_grades({"period_name": "1 Полугодие", "is_semester": True, "disciplines": disciplines})
    assert any(b.get("type") == "heading" and "Полугодие" in b.get("text", "") for b in blocks_s)


def test_rich_year_grades():
    year_grades_q = [
        {"name": "Алгебра", "grades": ["5", "4", "5", "5"], "yeargrade": "5"}
    ]
    blocks_q = rf.rich_year_grades(year_grades_q, is_semester=False)
    assert any(b.get("type") == "heading" and "четвертям" in b.get("text", "") for b in blocks_q)
    assert any(b.get("type") == "table" for b in blocks_q)

    year_grades_s = {
        "is_semester": True,
        "disciplines": [
            {"name": "Геометрия", "grades": ["4", "3"], "yeargrade": "3"}
        ]
    }
    blocks_s = rf.rich_year_grades(year_grades_s)
    assert any(b.get("type") == "heading" and "полугодиям" in b.get("text", "") for b in blocks_s)
    table_block = next(b for b in blocks_s if b.get("type") == "table")
    # Header cells for semester: Предмет, I, II, Год (4 columns)
    assert len(table_block["cells"][0]) == 4


def test_rich_calls():
    blocks = rf.rich_calls()
    assert any(b.get("type") == "heading" for b in blocks)
    assert any(b.get("type") == "table" for b in blocks)
    assert any(b.get("type") == "buttons" for b in blocks)


def test_rich_help():
    blocks = rf.rich_help()
    assert any(b.get("type") == "heading" for b in blocks)
    assert any(b.get("type") == "buttons" for b in blocks)


def test_rich_start():
    blocks_unreg = rf.rich_start(is_registered=False, webapp_url="https://example.com")
    assert any(b.get("type") == "heading" for b in blocks_unreg)
    assert any(b.get("type") == "buttons" for b in blocks_unreg)

    blocks_reg = rf.rich_start(is_registered=True, student_name="Иван")
    assert any(b.get("type") == "heading" for b in blocks_reg)
    assert any(b.get("type") == "buttons" for b in blocks_reg)


def test_rich_profile():
    p = {"firstName": "Иван", "lastName": "Иванов", "className": "10В", "orgName": "Лицей 1"}
    blocks = rf.rich_profile(p, "2025", is_semester=True)
    assert any(b.get("type") == "heading" for b in blocks)
    assert any(b.get("type") == "table" for b in blocks)
    assert any(b.get("type") == "buttons" for b in blocks)


def test_rich_grades_menu():
    periods = [{"name": "1 Полугодие"}, {"name": "2 Полугодие"}]
    blocks = rf.rich_grades_menu(periods, is_semester=True, school_year="2025")
    assert any(b.get("type") == "heading" for b in blocks)
    assert any(b.get("type") == "buttons" for b in blocks)


def test_rich_year_selection():
    years = [{"id": "2025", "text": "2025/2026"}, {"id": "2024", "text": "2024/2025"}]
    blocks = rf.rich_year_selection(years, "2025")
    assert any(b.get("type") == "heading" for b in blocks)
    assert any(b.get("type") == "buttons" for b in blocks)


def test_rich_schedule_with_dict_and_date():
    sched = {
        "day_idx": 2,
        "date": "2025-05-14T00:00:00.000+05:00",
        "lessons": [
            {"num": 1, "name": "Алгебра", "room": "204", "beginHour": 8, "beginMinute": 30, "endHour": 9, "endMinute": 10}
        ]
    }
    blocks = rf.rich_schedule(2, sched)
    assert any(b.get("type") == "heading" and "14.05.2025" in b.get("text", "") for b in blocks)
    assert any(b.get("type") == "table" for b in blocks)


def test_rich_new_grades_notification():
    new_grades = [
        {"subject": "Химия", "grade": "5", "average": 4.5}
    ]
    blocks = rf.rich_new_grades_notification(new_grades)
    assert any(b.get("type") == "heading" and "Новые оценки" in b.get("text", "") for b in blocks)
    assert any(b.get("type") == "table" for b in blocks)
