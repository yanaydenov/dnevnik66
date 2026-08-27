from typing import Optional, Dict, Any, List, Union
from datetime import datetime
from formatters import WEEKDAYS, format_file_plural


def _cell(text: Any) -> Dict[str, str]:
    return {"text": str(text) if text is not None else ""}


def rich_schedule(day_idx: int, lessons: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Generates Telegram Rich Message blocks with native Table for schedule"""
    weekday = WEEKDAYS[day_idx] if 0 <= day_idx < len(WEEKDAYS) else "Расписание"

    blocks: List[Dict[str, Any]] = [
        {"type": "heading", "text": f"🗓 {weekday}", "size": 1},
        {"type": "divider"},
    ]

    if day_idx == 6 or not lessons:
        blocks.append({"type": "paragraph", "text": "🛋 В этот день уроков нет"})
        return blocks

    # Table rows: № | Время | Предмет | Каб.
    table_cells: List[List[Dict[str, str]]] = [
        [_cell("№"), _cell("Время"), _cell("Предмет"), _cell("Каб.")]
    ]

    for idx, l in enumerate(lessons):
        num = str(l.get("num") or (idx + 1))
        name = str(l.get("name") or "")
        room = str(l.get("room") or "—")

        bh, bm = l.get("beginHour"), l.get("beginMinute")
        eh, em = l.get("endHour"), l.get("endMinute")

        time_str = f"{bh:02d}:{bm:02d}–{eh:02d}:{em:02d}" if (bh is not None and eh is not None) else "—"

        table_cells.append([
            _cell(num),
            _cell(time_str),
            _cell(name),
            _cell(room)
        ])

    blocks.append({
        "type": "table",
        "is_compact": True,
        "cells": table_cells,
    })

    return blocks


def rich_homework(hw: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Generates Telegram Rich Message blocks with native Details/Accordions for homework"""
    date_raw = hw.get("date", "0001-01-01")
    try:
        parts = [int(i) for i in date_raw.split("-")]
        dt = datetime(parts[0], parts[1], parts[2])
        header_title = f"🗓 {WEEKDAYS[dt.weekday()]} • {parts[2]:02d}.{parts[1]:02d}.{parts[0]}"
    except Exception:
        header_title = f"🗓 {date_raw}"

    blocks: List[Dict[str, Any]] = [
        {"type": "heading", "text": header_title, "size": 1},
        {"type": "divider"},
    ]

    homework_list = hw.get("homework", [])
    if not homework_list:
        blocks.append({"type": "paragraph", "text": "✨ На этот день домашних заданий нет"})
        return blocks

    for item in homework_list:
        name = item.get("lessonName", "") or "Урок"
        desc = (item.get("description") or "").strip() or "Нет описания задания"
        files = item.get("files", [])
        files_count = len(files) if files else item.get("filesCount", 0)

        files_str = f" (📎 {files_count} {format_file_plural(files_count)})" if files_count > 0 else ""
        title_str = f"📖 {name}{files_str}"

        # Native accordion details block
        blocks.append({
            "type": "details",
            "summary": title_str,
            "blocks": [
                {"type": "paragraph", "text": desc}
            ]
        })

    return blocks


def rich_period_grades(
    period: Union[int, str, Dict[str, Any]],
    disciplines: Optional[List[Dict[str, Any]]] = None,
    is_semester: bool = False,
) -> List[Dict[str, Any]]:
    """Generates Telegram Rich Message blocks with native Table for quarter or semester grades"""
    if isinstance(period, dict):
        period_title = period.get("period_name") or f"Период {period.get('period_idx', 0) + 1}"
        disciplines = period.get("disciplines") or []
        is_semester = period.get("is_semester", is_semester)
    elif isinstance(period, int):
        period_word = "полугодие" if is_semester else "четверть"
        period_title = f"{period} {period_word}"
    else:
        period_title = str(period)

    blocks: List[Dict[str, Any]] = [
        {"type": "heading", "text": f"📊 Оценки за {period_title}", "size": 1},
        {"type": "divider"},
    ]

    disciplines = disciplines or []
    has_grades = False
    table_cells: List[List[Dict[str, str]]] = [
        [_cell("Предмет"), _cell("Оценки"), _cell("Ср."), _cell("Взвеш.")]
    ]

    for d in disciplines:
        grades_list = d.get("grades", [])
        if not grades_list:
            continue

        has_grades = True
        flat_grades = []
        for g in grades_list:
            if isinstance(g, list):
                flat_grades.append("/".join(str(x) for x in g))
            else:
                flat_grades.append(str(g))

        grades_str = ", ".join(flat_grades) if flat_grades else "—"
        avg = str(round(float(d.get("average", 0.0) or 0.0), 2))
        avg_w = str(round(float(d.get("averagew", 0.0) or 0.0), 2))

        table_cells.append([
            _cell(d.get("name", "")),
            _cell(grades_str),
            _cell(avg),
            _cell(avg_w),
        ])

    if has_grades:
        blocks.append({
            "type": "table",
            "is_compact": True,
            "cells": table_cells,
        })
    else:
        blocks.append({"type": "paragraph", "text": "✨ Оценок за этот период пока нет"})

    return blocks


def rich_week_grades(grades_dict: Dict[str, List[Any]]) -> List[Dict[str, Any]]:
    """Generates Telegram Rich Message blocks with native Table for weekly grades"""
    blocks: List[Dict[str, Any]] = [
        {"type": "heading", "text": "🗓 Оценки на этой неделе", "size": 1},
        {"type": "divider"},
    ]

    if not grades_dict:
        blocks.append({"type": "paragraph", "text": "✨ Оценок на этой неделе пока нет"})
        return blocks

    table_cells: List[List[Dict[str, str]]] = [
        [_cell("Предмет"), _cell("Оценки")]
    ]
    has_any = False

    for name, grades in grades_dict.items():
        if not grades:
            continue
        has_any = True
        flat_grades = []
        for g in grades:
            if isinstance(g, list):
                flat_grades.append("/".join(str(x) for x in g))
            else:
                flat_grades.append(str(g))

        table_cells.append([
            _cell(name),
            _cell(", ".join(flat_grades))
        ])

    if has_any:
        blocks.append({
            "type": "table",
            "is_compact": True,
            "cells": table_cells,
        })
    else:
        blocks.append({"type": "paragraph", "text": "✨ Оценок на этой неделе пока нет"})

    return blocks


def rich_year_grades(
    year_grades: Union[List[Dict[str, Any]], Dict[str, Any]],
    is_semester: bool = False
) -> List[Dict[str, Any]]:
    """Generates Telegram Rich Message blocks with native Table for quarter/semester and final grades"""
    if isinstance(year_grades, dict):
        items = year_grades.get("disciplines") or year_grades.get("items") or []
        is_semester = year_grades.get("is_semester", is_semester)
    else:
        items = year_grades

    period_type_label = "полугодиям" if is_semester else "четвертям"
    blocks: List[Dict[str, Any]] = [
        {"type": "heading", "text": f"📑 Оценки по {period_type_label} и итог", "size": 1},
        {"type": "divider"},
    ]

    if not items:
        blocks.append({"type": "paragraph", "text": f"✨ Оценки по {period_type_label} пока отсутствуют"})
        return blocks

    if is_semester:
        table_cells: List[List[Dict[str, str]]] = [
            [_cell("Предмет"), _cell("I"), _cell("II"), _cell("Год")]
        ]
        for item in items:
            name = item.get("name", "")
            grades = list(item.get("grades", ["━", "━"]))
            year_grade = item.get("yeargrade", "━")

            while len(grades) < 2:
                grades.append("━")

            table_cells.append([
                _cell(name),
                _cell(grades[0]),
                _cell(grades[1]),
                _cell(year_grade)
            ])
    else:
        table_cells: List[List[Dict[str, str]]] = [
            [_cell("Предмет"), _cell("I"), _cell("II"), _cell("III"), _cell("IV"), _cell("Год")]
        ]
        for item in items:
            name = item.get("name", "")
            grades = list(item.get("grades", ["━", "━", "━", "━"]))
            year_grade = item.get("yeargrade", "━")

            while len(grades) < 4:
                grades.append("━")

            table_cells.append([
                _cell(name),
                _cell(grades[0]),
                _cell(grades[1]),
                _cell(grades[2]),
                _cell(grades[3]),
                _cell(year_grade)
            ])

    blocks.append({
        "type": "table",
        "is_compact": True,
        "cells": table_cells,
    })

    return blocks


def rich_calls() -> List[Dict[str, Any]]:
    """Generates Telegram Rich Message blocks with native Table for call schedule"""
    return [
        {"type": "heading", "text": "🔔 Расписание звонков", "size": 1},
        {"type": "divider"},
        {
            "type": "table",
            "is_compact": True,
            "cells": [
                [_cell("Урок"), _cell("Время"), _cell("Перемена")],
                [_cell("1"), _cell("08:30 — 09:10"), _cell("10 мин")],
                [_cell("2"), _cell("09:20 — 10:00"), _cell("20 мин")],
                [_cell("3"), _cell("10:20 — 11:00"), _cell("20 мин")],
                [_cell("4"), _cell("11:20 — 12:00"), _cell("20 мин")],
                [_cell("5"), _cell("12:20 — 13:00"), _cell("10 мин")],
                [_cell("6"), _cell("13:10 — 13:50"), _cell("15 мин")],
                [_cell("7"), _cell("14:05 — 14:45"), _cell("10 мин")],
                [_cell("8"), _cell("14:55 — 15:35"), _cell("—")]
            ]
        }
    ]


def rich_help() -> List[Dict[str, Any]]:
    """Generates Telegram Rich Message blocks for help menu"""
    return [
        {"type": "heading", "text": "🎓 Телеграм-бот «Школьный дневник»", "size": 1},
        {"type": "divider"},
        {"type": "heading", "text": "🛠 Аккаунт и сервис", "size": 2},
        {"type": "paragraph", "text": "• /login — Подключение и вход через Дневник\n• /profile — Профиль ученика и школа\n• /help — Справка и команды\n• /delacc — Удалить аккаунт из бота"},
        {"type": "divider"},
        {"type": "heading", "text": "📅 Расписание", "size": 2},
        {"type": "paragraph", "text": "• /today — Расписание на сегодня\n• /nextday — Расписание на завтра\n• /all — Выбор любого дня недели\n• /calls — Расписание звонков"},
        {"type": "divider"},
        {"type": "heading", "text": "📊 Оценки", "size": 2},
        {"type": "paragraph", "text": "• /wgrades — Оценки на этой неделе\n• /pgrades — Четвертные и итоговые оценки\n• /grades — Меню выбора четверти"},
        {"type": "divider"},
        {"type": "heading", "text": "✍️ Домашнее задание", "size": 2},
        {"type": "paragraph", "text": "• /homework — Домашнее задание с перелистыванием дат"},
    ]
