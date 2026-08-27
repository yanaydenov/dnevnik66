import math
from typing import Optional, Dict, Any, List, Union
from datetime import datetime

SPEC_CHARS = ['\\', '_', '*', '[', ']', '(', ')', '~', '`', '>', '<', '&', '#', '+', '-', '=', '|', '{', '}', '.', '!']
WEEKDAYS = ['Понедельник', 'Вторник', 'Среда', 'Четверг', 'Пятница', 'Суббота', 'Воскресенье']


def esc_md(text: Any) -> str:
    """Escape text for MarkdownV2"""
    if text is None:
        return ""
    s = str(text)
    for char in SPEC_CHARS:
        s = s.replace(char, f"\\{char}")
    return s


def format_grade_badge(grade: Any) -> str:
    """Colored grade badge: 🟢 5, 🟢 4, 🟡 3, 🔴 2, 🔴 1"""
    if grade is None or grade == "" or grade == "━":
        return "━"
    s = str(grade).strip()
    if s.startswith("5") or s.startswith("4"):
        return f"🟢 {esc_md(s)}"
    elif s.startswith("3"):
        return f"🟡 {esc_md(s)}"
    elif s.startswith("2") or s.startswith("1"):
        return f"🔴 {esc_md(s)}"
    return esc_md(s)


def format_multi_grade(grades: Union[List[Any], str]) -> str:
    if isinstance(grades, list):
        if not grades:
            return ""
        joined = "/".join(str(g) for g in grades)
        return format_grade_badge(joined)
    return format_grade_badge(grades)


def format_file_plural(count: int) -> str:
    words = ['файлов', 'файл', 'файла', 'файла', 'файла', 'файлов', 'файлов', 'файлов', 'файлов', 'файлов']
    if count % 100 in (11, 12, 13, 14):
        return "файлов"
    return words[count % 10]


def format_homework_message(hw: Dict[str, Any]) -> str:
    date_raw = hw.get("date", "0001-01-01")
    try:
        parts = [int(i) for i in date_raw.split("-")]
        dt = datetime(parts[0], parts[1], parts[2])
        header = f"{WEEKDAYS[dt.weekday()]} • {parts[2]}-{parts[1]}-{parts[0]}"
    except Exception:
        header = date_raw

    res = esc_md(header) + "\n\n"

    homework_list = hw.get("homework", [])
    if homework_list:
        for item in homework_list:
            name = item.get("lessonName", "")
            desc = item.get("description", "Нет задания")
            files_count = item.get("filesCount", 0)

            files_str = ""
            if files_count > 0:
                files_str = f" \\(📎 {files_count} {format_file_plural(files_count)}\\)"

            res += f"{esc_md(name)}{files_str}:\n>{esc_md(desc)}||\n\n"
    else:
        res += "*Нет домашних заданий*"

    return res


def format_schedule_message(day_idx: int, lessons: List[Dict[str, Any]]) -> str:
    res = esc_md(WEEKDAYS[day_idx]) + "\n\n"
    if day_idx == 6 or not lessons:
        res += "*В этот день уроков нет*"
        return res

    for l in lessons:
        num = l.get("num", "")
        name = l.get("name", "")
        room = l.get("room", "")

        bh, bm = l.get("beginHour"), l.get("beginMinute")
        eh, em = l.get("endHour"), l.get("endMinute")

        time_str = ""
        if bh is not None and bm is not None and eh is not None and em is not None:
            time_str = f"{bh:02d}:{bm:02d}\\.{eh:02d}:{em:02d} · "

        room_str = f" • {esc_md(room)}" if room else ""
        res += f"{esc_md(num)} │ {time_str}{esc_md(name)}{room_str}\n"

    return res


def format_period_grades_message(period_num: int, disciplines: List[Dict[str, Any]]) -> str:
    res = f"{period_num} четверть\n\n"
    has_grades = False

    for d in disciplines:
        grades_list = d.get("grades", [])
        if not grades_list:
            continue

        has_grades = True
        formatted_grades = []
        for g in grades_list:
            if isinstance(g, list):
                formatted_grades.append(format_multi_grade(g))
            else:
                formatted_grades.append(format_grade_badge(g))

        grades_str = " • ".join(formatted_grades)
        avg = round(d.get("average", 0.0), 2)
        avg_w = round(d.get("averagew", 0.0), 2)

        res += f"{esc_md(d.get('name', ''))} • {esc_md(avg)} \\(ср\\.взвеш: {esc_md(avg_w)}\\)\n"
        res += f"└ {grades_str}\n\n"

    if not has_grades:
        res += "*Нет оценок*"

    return res


def format_week_grades_message(grades_dict: Dict[str, List[Any]]) -> str:
    if not grades_dict:
        return "Текущая неделя\n\n*Нет оценок*"

    res = "Текущая неделя\n\n"
    for name, grades in grades_dict.items():
        if not grades:
            continue
        formatted = []
        for g in grades:
            if isinstance(g, list):
                formatted.append(format_multi_grade(g))
            else:
                formatted.append(format_grade_badge(g))

        res += f"{esc_md(name)}\n"
        res += f"└ {' • '.join(formatted)}\n\n"

    return res


def format_year_grades_message(year_grades: List[Dict[str, Any]]) -> str:
    if not year_grades:
        return "Четвертные оценки пока отсутствуют"

    res = "Четвертные оценки\n\n"
    for item in year_grades:
        name = item.get("name", "")
        grades = item.get("grades", ["━", "━", "━", "━"])
        year_grade = item.get("yeargrade", "━")

        badges = [format_grade_badge(g) for g in grades]
        res += f"{esc_md(name)}\n"
        res += f"└ {' • '.join(badges)}   Итог: {format_grade_badge(year_grade)}\n\n"

    return res


def format_calls_message() -> str:
    return (
        "🔔 *Расписание звонков*\n\n"
        "1 │ 8:30 — 9:10\n"
        "2 │ 9:20 — 10:00\n"
        "3 │ 10:20 — 11:00\n"
        "4 │ 11:20 — 12:00\n"
        "5 │ 12:20 — 13:00\n"
        "6 │ 13:10 — 13:50\n"
        "7 │ 14:05 — 14:45\n"
        "8 │ 14:55 — 15:35"
    )


def format_help_message() -> str:
    return (
        "🛠 *Сервис*\n"
        "/login • Регистрация и подключение\n"
        "/help • Это меню справки\n"
        "/profile • Информация об аккаунте\n"
        "/delacc • Удалить аккаунт из бота\n\n"
        "📅 *Расписание*\n"
        "/all • Расписание на любой день недели\n"
        "/today • Расписание на сегодня\n"
        "/nextday • Расписание на завтра\n"
        "/calls • Расписание звонков\n\n"
        "📋 *Оценки*\n"
        "/grades • Все оценки и четверти\n"
        "/wgrades • Оценки на этой неделе\n"
        "/pgrades • Четвертные оценки\n\n"
        "✍️ *Домашнее задание*\n"
        "/homework • Домашнее задание по дням"
    )
