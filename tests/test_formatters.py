import pytest
from formatters import (
    esc_md,
    format_grade_badge,
    format_multi_grade,
    format_schedule_message,
    format_homework_message,
    format_period_grades_message,
    format_week_grades_message,
    format_year_grades_message,
    format_calls_message,
    format_help_message,
)


def test_esc_md():
    assert esc_md("hello.world!") == "hello\\.world\\!"
    assert esc_md("test_1*2") == "test\\_1\\*2"
    assert esc_md(None) == ""


def test_format_grade_badge():
    assert format_grade_badge("5") == "🟢 5"
    assert format_grade_badge("4") == "🟢 4"
    assert format_grade_badge("3") == "🟡 3"
    assert format_grade_badge("2") == "🔴 2"
    assert format_grade_badge("1") == "🔴 1"
    assert format_grade_badge(None) == "━"


def test_format_multi_grade():
    assert format_multi_grade(["5", "4"]) == "🟢 5/4"
    assert format_multi_grade(["3", "2"]) == "🟡 3/2"
    assert format_multi_grade([]) == ""


def test_format_schedule_message():
    lessons = [
        {"num": "1", "name": "Математика", "room": "204", "beginHour": 8, "beginMinute": 30, "endHour": 9, "endMinute": 10}
    ]
    res = format_schedule_message(0, lessons)
    assert "Понедельник" in res
    assert "Математика" in res
    assert "204" in res


def test_format_homework_message():
    hw = {
        "date": "2024-09-02",
        "homework": [
            {
                "lessonName": "Русский язык",
                "description": "Упр. 45",
                "filesCount": 1,
            }
        ]
    }
    res = format_homework_message(hw)
    assert "Русский язык" in res
    assert "Упр\\. 45" in res
    assert "**>" in res
    assert "||" in res


def test_format_period_grades_message():
    disciplines = [
        {
            "name": "Алгебра",
            "grades": [["5"], ["4", "5"]],
            "average": 4.67,
            "averagew": 4.75,
        }
    ]
    res = format_period_grades_message(1, disciplines)
    assert "1 четверть" in res
    assert "Алгебра" in res
    assert "🟢 5" in res


def test_format_week_grades_message():
    grades = {"Русский язык": [["5", "5"], ["4"]]}
    res = format_week_grades_message(grades)
    assert "Оценки на этой неделе" in res
    assert "Русский язык" in res
    assert "🟢 5/5" in res


def test_format_year_grades_message():
    year_grades = [
        {"name": "История", "grades": ["5", "4", "5", "5"], "yeargrade": "5"}
    ]
    res = format_year_grades_message(year_grades)
    assert "Четвертные и итоговые оценки" in res
    assert "История" in res
    assert "Итог:" in res
    assert "🟢 5" in res


def test_format_calls_message():
    calls = format_calls_message()
    assert "Расписание звонков" in calls
    assert "08:30" in calls


def test_format_help_message():
    help_msg = format_help_message()
    assert "/login" in help_msg
    assert "/today" in help_msg
    assert "/homework" in help_msg
    assert "/grades" in help_msg
