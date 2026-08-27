from typing import Optional, Dict, Any, List, Union
from datetime import datetime, timedelta
from formatters import WEEKDAYS, format_file_plural, parse_date_str, format_date_dmy


def _cell(text: Any) -> Dict[str, str]:
    return {"text": str(text) if text is not None else ""}


def _btn_cb(text: str, data: str) -> Dict[str, str]:
    return {"type": "callback", "text": text, "callback_data": data}


def _btn_url(text: str, url: str) -> Dict[str, str]:
    return {"type": "url", "text": text, "url": url}


def _btn_webapp(text: str, url: str) -> Dict[str, str]:
    return {"type": "web_app", "text": text, "url": url}


# -------------------------------------------------------------
# Rich Start & Welcome Screen
# -------------------------------------------------------------

def rich_start(is_registered: bool = False, student_name: str = "", webapp_url: str = "") -> List[Dict[str, Any]]:
    """Generates Telegram Rich Message for /start welcome menu"""
    blocks: List[Dict[str, Any]] = [
        {"type": "heading", "text": "🎓 Электронный дневник Свердловской области", "size": 1},
        {"type": "divider"},
    ]

    if not is_registered:
        blocks.extend([
            {"type": "paragraph", "text": "Привет! 👋 Я бот для удобного доступа к школьному электронному дневнику.\n\n✨ Возможности бота:\n• 🗓 Расписание уроков с временем и кабинетами\n• ✍️ Домашние задания со спойлерами и файлами\n• 📊 Четвертные, полугодовые и итоговые оценки\n• 🔔 Расписание звонков и перемен\n\nДля входа нажмите кнопку «✏️ Войти через WebApp» внизу экрана 👇"},
            {"type": "divider"},
        ])
        btn_row = [
            _btn_cb("✏️ Войти / Регистрация", "reg"),
            _btn_cb("📖 Список команд", "help"),
        ]
        blocks.append({"type": "buttons", "buttons": btn_row})
    else:
        name_str = f", {student_name}" if student_name else ""
        blocks.extend([
            {"type": "paragraph", "text": f"С возвращением{name_str}! 👋\nВыберите нужный раздел или воспользуйтесь быстрыми кнопками:"},
            {"type": "divider"},
            {"type": "buttons", "buttons": [
                _btn_cb("🗓 Расписание на сегодня", "today_quick"),
                _btn_cb("📅 На завтра", "nextday_quick"),
            ]},
            {"type": "buttons", "buttons": [
                _btn_cb("📋 Все оценки", "grades_menu"),
                _btn_cb("✍️ Домашние задания", "hw_quick"),
            ]},
            {"type": "buttons", "buttons": [
                _btn_cb("🔔 Звонки", "calls_quick"),
                _btn_cb("👤 Профиль", "profile_quick"),
                _btn_cb("🗓 Сменить год", "select_year"),
            ]},
        ])

    return blocks


# -------------------------------------------------------------
# Rich Schedule with In-Message Day Buttons & Dates
# -------------------------------------------------------------

def rich_schedule(
    day_idx: int,
    lessons: Union[List[Dict[str, Any]], Dict[str, Any]],
    day_date: Optional[str] = None
) -> List[Dict[str, Any]]:
    """Generates Telegram Rich Message blocks with native Table, exact dates, and day switcher buttons"""
    lessons_list: List[Dict[str, Any]] = []
    is_test_fallback = False

    if isinstance(lessons, dict):
        lessons_list = lessons.get("lessons") or []
        day_date = lessons.get("date") or day_date
        is_test_fallback = lessons.get("is_test_fallback", False)
    elif isinstance(lessons, list):
        lessons_list = lessons

    weekday = WEEKDAYS[day_idx] if 0 <= day_idx < len(WEEKDAYS) else "Расписание"

    date_title = ""
    dt_obj = None
    if day_date:
        dt_obj = parse_date_str(day_date)
        if dt_obj:
            date_title = f" • {dt_obj.day:02d}.{dt_obj.month:02d}.{dt_obj.year}"
        else:
            clean_str = str(day_date).split("T")[0]
            date_title = f" • {clean_str}"

    heading_text = f"🗓 {weekday}{date_title}"
    blocks: List[Dict[str, Any]] = [
        {"type": "heading", "text": heading_text, "size": 1},
        {"type": "divider"},
    ]

    if day_idx == 6 or not lessons_list:
        blocks.append({"type": "paragraph", "text": "🛋 В этот день уроков нет"})
    else:
        table_cells: List[List[Dict[str, str]]] = [
            [_cell("№"), _cell("Время"), _cell("Предмет"), _cell("Каб.")]
        ]
        for idx, l in enumerate(lessons_list):
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

    # Embedded in-message day switcher buttons (clean day names)
    days_short = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб"]
    day_btns = []
    for idx, name in enumerate(days_short):
        text = f"• {name} •" if idx == day_idx else name
        day_btns.append(_btn_cb(text, f"schedule{idx}"))

    blocks.append({"type": "divider"})
    # Split day buttons into 2 rows of 3 buttons for optimal readability
    blocks.append({"type": "buttons", "buttons": day_btns[:3]})
    blocks.append({"type": "buttons", "buttons": day_btns[3:]})
    blocks.append({"type": "buttons", "buttons": [
        _btn_cb("🔔 Звонки", "calls_quick"),
        _btn_cb("📋 Оценки", "grades_menu"),
        _btn_cb("✍️ ДЗ", "hw_quick"),
    ]})

    return blocks


# -------------------------------------------------------------
# Rich Homework with Attachment Download Buttons
# -------------------------------------------------------------

def rich_homework(hw: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Generates Telegram Rich Message blocks with native Details/Accordions and file download buttons"""
    date_raw = hw.get("date", "0001-01-01")
    dt = parse_date_str(date_raw)
    if dt:
        header_title = f"🗓 {WEEKDAYS[dt.weekday()]} • {dt.day:02d}.{dt.month:02d}.{dt.year}"
    else:
        header_title = f"🗓 {str(date_raw).split('T')[0]}"

    blocks: List[Dict[str, Any]] = [
        {"type": "heading", "text": header_title, "size": 1},
        {"type": "divider"},
    ]

    homework_list = hw.get("homework", [])
    all_files = []

    if not homework_list:
        blocks.append({"type": "paragraph", "text": "✨ На этот день домашних заданий нет"})
    else:
        for item in homework_list:
            name = item.get("lessonName", "") or "Урок"
            desc = (item.get("description") or "").strip() or "Нет описания задания"
            files = item.get("files", [])
            files_count = len(files) if files else item.get("filesCount", 0)

            for f in files:
                all_files.append(f)

            files_str = f" (📎 {files_count} {format_file_plural(files_count)})" if files_count > 0 else ""
            title_str = f"📖 {name}{files_str}"

            blocks.append({
                "type": "details",
                "summary": title_str,
                "blocks": [
                    {"type": "paragraph", "text": desc}
                ]
            })

    # Add file download buttons if there are attachments
    if all_files:
        blocks.append({"type": "divider"})
        file_btns = []
        for f in all_files[:6]:  # Show up to 6 direct download buttons
            f_name = f.get("name", "Файл")
            f_id = f.get("id", "")
            if f_id:
                file_btns.append(_btn_cb(f"📥 {f_name[:20]}", f"dlfile_{f_id}"))
        if file_btns:
            # 2 files per row
            for i in range(0, len(file_btns), 2):
                blocks.append({"type": "buttons", "buttons": file_btns[i:i + 2]})

    pagination = hw.get("pages", {})
    prev_date = pagination.get("previousDate")
    next_date = pagination.get("nextDate")
    has_prev = bool(prev_date and prev_date != "0001-01-01")
    has_next = bool(next_date and next_date != "0001-01-01")

    nav_btns = [
        _btn_cb("◀️ Назад", f"hw{prev_date}") if has_prev else _btn_cb("🚫", "hwnoop"),
        _btn_cb("📅 Сегодня", "hwtoday"),
        _btn_cb("Вперёд ▶️", f"hw{next_date}") if has_next else _btn_cb("🚫", "hwnoop"),
    ]

    blocks.append({"type": "divider"})
    blocks.append({"type": "buttons", "buttons": nav_btns})
    blocks.append({"type": "buttons", "buttons": [
        _btn_cb("🗓 Расписание", "schedule0"),
        _btn_cb("📋 Оценки", "grades_menu"),
    ]})

    return blocks


# -------------------------------------------------------------
# Rich Period & Year Grades with In-Message Quarter/Semester Buttons
# -------------------------------------------------------------

def rich_period_grades(
    period: Union[int, str, Dict[str, Any]],
    disciplines: Optional[List[Dict[str, Any]]] = None,
    is_semester: bool = False,
    study_periods: Optional[List[Dict[str, Any]]] = None,
) -> List[Dict[str, Any]]:
    """Generates Telegram Rich Message blocks with native Table and in-message period switcher"""
    selected_idx = 0
    if isinstance(period, dict):
        period_title = period.get("period_name") or f"Период {period.get('period_idx', 0) + 1}"
        selected_idx = period.get("period_idx", 0)
        disciplines = period.get("disciplines") or []
        is_semester = period.get("is_semester", is_semester)
    elif isinstance(period, int):
        selected_idx = period - 1
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

    # In-message period navigation buttons
    blocks.append({"type": "divider"})
    row_btns = []
    periods_count = 2 if is_semester else 4
    for idx in range(periods_count):
        label = f"{idx + 1} полуг." if is_semester else f"{idx + 1} четв"
        text = f"• {label} •" if idx == selected_idx else label
        row_btns.append(_btn_cb(text, f"pgrades{idx}"))
    row_btns.append(_btn_cb("Год 📑", "ygrades"))

    blocks.append({"type": "buttons", "buttons": row_btns})
    blocks.append({"type": "buttons", "buttons": [
        _btn_cb("📋 Оценки на этой неделе", "wgrades"),
        _btn_cb("📊 Меню оценок", "grades_menu"),
    ]})

    return blocks


def rich_week_grades(grades_dict: Dict[str, List[Any]], is_semester: bool = False) -> List[Dict[str, Any]]:
    """Generates Telegram Rich Message blocks with native Table for weekly grades"""
    blocks: List[Dict[str, Any]] = [
        {"type": "heading", "text": "🗓 Оценки на этой неделе", "size": 1},
        {"type": "divider"},
    ]

    if not grades_dict:
        blocks.append({"type": "paragraph", "text": "✨ Оценок на этой неделе пока нет"})
    else:
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

    # Navigation buttons
    blocks.append({"type": "divider"})
    row_btns = []
    periods_count = 2 if is_semester else 4
    for idx in range(periods_count):
        label = f"{idx + 1} полуг." if is_semester else f"{idx + 1} четв"
        row_btns.append(_btn_cb(label, f"pgrades{idx}"))
    row_btns.append(_btn_cb("Год 📑", "ygrades"))

    blocks.append({"type": "buttons", "buttons": row_btns})
    blocks.append({"type": "buttons", "buttons": [
        _btn_cb("📊 Меню оценок", "grades_menu"),
        _btn_cb("🗓 Расписание", "schedule0"),
    ]})

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
    else:
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

    # In-message navigation buttons
    blocks.append({"type": "divider"})
    row_btns = []
    periods_count = 2 if is_semester else 4
    for idx in range(periods_count):
        label = f"{idx + 1} полуг." if is_semester else f"{idx + 1} четв"
        row_btns.append(_btn_cb(label, f"pgrades{idx}"))
    row_btns.append(_btn_cb("• Год •", "ygrades"))

    blocks.append({"type": "buttons", "buttons": row_btns})
    blocks.append({"type": "buttons", "buttons": [
        _btn_cb("📋 Оценки на этой неделе", "wgrades"),
        _btn_cb("📊 Меню оценок", "grades_menu"),
    ]})

    return blocks


# -------------------------------------------------------------
# Rich Grades Menu Screen
# -------------------------------------------------------------

def rich_grades_menu(study_periods: List[Dict[str, Any]], is_semester: bool, school_year: str) -> List[Dict[str, Any]]:
    """Generates rich menu for /grades with all period options as buttons in message"""
    sys_type = "полугодовая" if is_semester else "четвертная"
    blocks: List[Dict[str, Any]] = [
        {"type": "heading", "text": "📊 Оценки ученика", "size": 1},
        {"type": "divider"},
        {"type": "paragraph", "text": f"📅 Учебный год: {school_year}\n🏫 Система обучения: {sys_type}\n\nВыберите период для просмотра оценок:"},
        {"type": "divider"},
        {"type": "buttons", "buttons": [
            _btn_cb("📋 Оценки на этой неделе", "wgrades")
        ]},
    ]

    if is_semester:
        row = []
        for idx, p in enumerate(study_periods):
            name = p.get("name") or f"{idx + 1} полугодие"
            row.append(_btn_cb(name, f"pgrades{idx}"))
        if row:
            blocks.append({"type": "buttons", "buttons": row})
        blocks.append({"type": "buttons", "buttons": [
            _btn_cb("📑 Итоги по полугодиям (Год)", "ygrades")
        ]})
    else:
        row1, row2 = [], []
        for idx, p in enumerate(study_periods):
            name = p.get("name") or f"{idx + 1} четверть"
            if idx < 2:
                row1.append(_btn_cb(name, f"pgrades{idx}"))
            else:
                row2.append(_btn_cb(name, f"pgrades{idx}"))
        if row1:
            blocks.append({"type": "buttons", "buttons": row1})
        if row2:
            blocks.append({"type": "buttons", "buttons": row2})
        blocks.append({"type": "buttons", "buttons": [
            _btn_cb("📑 Итоги по четвертям (Год)", "ygrades")
        ]})

    blocks.append({"type": "buttons", "buttons": [
        _btn_cb("🗓 Сменить учебный год", "select_year")
    ]})

    return blocks


# -------------------------------------------------------------
# Rich Profile Screen
# -------------------------------------------------------------

def rich_profile(
    p: Dict[str, Any],
    school_year: str,
    is_semester: bool,
    notify_enabled: bool = True,
) -> List[Dict[str, Any]]:
    """Generates rich profile card with details, notification toggle, and action buttons"""
    last_name = p.get("lastName", "")
    first_name = p.get("firstName", "")
    sur_name = p.get("surName", "")
    full_name = f"{last_name} {first_name} {sur_name}".strip() or "Ученик"
    org_name = p.get("orgName", "Школа")
    class_name = p.get("className", "") or "—"
    sys_type = "Полугодия" if is_semester else "Четверти"
    notify_status = "Включены (каждые 40 мин)" if notify_enabled else "Отключены"

    return [
        {"type": "heading", "text": "👤 Профиль ученика", "size": 1},
        {"type": "divider"},
        {
            "type": "table",
            "is_compact": True,
            "cells": [
                [_cell("Параметр"), _cell("Значение")],
                [_cell("ФИО"), _cell(full_name)],
                [_cell("Школа"), _cell(org_name)],
                [_cell("Класс"), _cell(class_name)],
                [_cell("Учебный год"), _cell(school_year)],
                [_cell("Система"), _cell(sys_type)],
                [_cell("Оценки"), _cell(notify_status)],
            ]
        },
        {"type": "divider"},
        {"type": "buttons", "buttons": [
            _btn_cb(f"🔔 Уведомления: {'Вкл ✅' if notify_enabled else 'Выкл ❌'}", "toggle_notify"),
            _btn_cb("🗓 Сменить год", "select_year"),
        ]},
        {"type": "buttons", "buttons": [
            _btn_cb("📋 Все оценки", "grades_menu"),
            _btn_cb("✍️ Домашние задания", "hw_quick"),
        ]},
        {"type": "buttons", "buttons": [
            _btn_cb("🔔 Расписание звонков", "calls_quick"),
            _btn_cb("🗑 Удалить аккаунт", "deleteacc_prompt"),
        ]}
    ]


def rich_new_grades_notification(new_items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Generates Telegram Rich Message for newly received grades notification"""
    blocks: List[Dict[str, Any]] = [
        {"type": "heading", "text": "⚡️ Новые оценки в электронном дневнике!", "size": 1},
        {"type": "divider"},
    ]

    table_cells: List[List[Dict[str, str]]] = [
        [_cell("Предмет"), _cell("Новая оценка"), _cell("Ср. балл")]
    ]

    for item in new_items:
        subj = item.get("subject", "Предмет")
        new_g = item.get("grade", "")
        avg = str(round(float(item.get("average", 0.0) or 0.0), 2))
        table_cells.append([
            _cell(subj),
            _cell(new_g),
            _cell(avg),
        ])

    blocks.append({
        "type": "table",
        "is_compact": True,
        "cells": table_cells,
    })

    blocks.append({"type": "divider"})
    blocks.append({"type": "buttons", "buttons": [
        _btn_cb("📋 Все оценки", "grades_menu"),
        _btn_cb("🗓 Расписание", "schedule0"),
    ]})

    return blocks


# -------------------------------------------------------------
# Rich Year Selection Screen
# -------------------------------------------------------------

def rich_year_selection(years: List[Dict[str, str]], active_year: str) -> List[Dict[str, Any]]:
    """Generates rich school year switcher with embedded buttons"""
    blocks: List[Dict[str, Any]] = [
        {"type": "heading", "text": "🗓 Выбор учебного года", "size": 1},
        {"type": "divider"},
        {"type": "paragraph", "text": f"📅 Текущий активный год: {active_year or 'не задан'}\n\nВыберите учебный год для работы бота (расписание, оценки, ДЗ):"},
        {"type": "divider"},
    ]

    for y in years:
        y_id = y["id"]
        y_text = y["text"]
        mark = " ✅" if active_year == y_id else ""
        blocks.append({
            "type": "buttons",
            "buttons": [_btn_cb(f"📚 {y_text}{mark}", f"setyear_{y_id}")]
        })

    blocks.append({
        "type": "buttons",
        "buttons": [_btn_cb("◀️ Назад в меню", "back_to_grades")]
    })

    return blocks


# -------------------------------------------------------------
# Rich Calls Screen
# -------------------------------------------------------------

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
        },
        {"type": "divider"},
        {"type": "buttons", "buttons": [
            _btn_cb("🗓 Расписание уроков", "schedule0"),
            _btn_cb("📋 Оценки", "grades_menu"),
            _btn_cb("✍️ ДЗ", "hw_quick"),
        ]}
    ]


# -------------------------------------------------------------
# Rich Help Screen
# -------------------------------------------------------------

def rich_help() -> List[Dict[str, Any]]:
    """Generates Telegram Rich Message blocks for help menu with all commands and buttons"""
    return [
        {"type": "heading", "text": "📖 Меню и список команд", "size": 1},
        {"type": "divider"},
        {"type": "heading", "text": "📅 Расписание", "size": 2},
        {"type": "paragraph", "text": "• /today — Расписание на сегодня\n• /nextday — Расписание на завтра\n• /all — Расписание на любой день недели\n• /calls — Расписание звонков и перемен"},
        {"type": "divider"},
        {"type": "heading", "text": "📊 Оценки", "size": 2},
        {"type": "paragraph", "text": "• /grades — Главное меню оценок\n• /wgrades — Оценки на этой неделе\n• /pgrades — Оценки по четвертям / полугодиям и год"},
        {"type": "divider"},
        {"type": "heading", "text": "✍️ Домашнее задание", "size": 2},
        {"type": "paragraph", "text": "• /homework — Домашние задания со спойлерами и файлами"},
        {"type": "divider"},
        {"type": "heading", "text": "⚙️ Настройки и аккаунт", "size": 2},
        {"type": "paragraph", "text": "• /profile — Профиль ученика и школа\n• /year — Смена учебного года\n• /login — Авторизация через Дневник\n• /delacc — Удаление аккаунта"},
        {"type": "divider"},
        {"type": "buttons", "buttons": [
            _btn_cb("🗓 На сегодня", "today_quick"),
            _btn_cb("📅 На завтра", "nextday_quick"),
            _btn_cb("🗓 На всю неделю", "schedule0"),
        ]},
        {"type": "buttons", "buttons": [
            _btn_cb("📋 Все оценки", "grades_menu"),
            _btn_cb("✍️ Домашние задания", "hw_quick"),
        ]},
        {"type": "buttons", "buttons": [
            _btn_cb("🔔 Звонки", "calls_quick"),
            _btn_cb("👤 Профиль", "profile_quick"),
            _btn_cb("🗓 Сменить год", "select_year"),
        ]},
    ]
