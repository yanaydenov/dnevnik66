from typing import Optional, Dict, Any, List, Union
from datetime import datetime

SPEC_CHARS = ['\\', '_', '*', '[', ']', '(', ')', '~', '`', '>', '<', '&', '#', '+', '-', '=', '|', '{', '}', '.', '!']
WEEKDAYS = ['Понедельник', 'Вторник', 'Среда', 'Четверг', 'Пятница', 'Суббота', 'Воскресенье']
NUM_EMOJIS = ['1️⃣', '2️⃣', '3️⃣', '4️⃣', '5️⃣', '6️⃣', '7️⃣', '8️⃣', '9️⃣', '🔟']


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
    """
    Formats homework using Telegram Expandable Blockquotes (**> ... ||)
    for sleek expandable descriptions.
    """
    date_raw = hw.get("date", "0001-01-01")
    try:
        parts = [int(i) for i in date_raw.split("-")]
        dt = datetime(parts[0], parts[1], parts[2])
        header = f"🗓 *{esc_md(WEEKDAYS[dt.weekday()])} • {parts[2]:02d}\\.{parts[1]:02d}\\.{parts[0]}*"
    except Exception:
        header = f"🗓 *{esc_md(date_raw)}*"

    res = header + "\n\n"

    homework_list = hw.get("homework", [])
    if homework_list:
        for item in homework_list:
            name = item.get("lessonName", "") or "Урок"
            desc = (item.get("description") or "").strip() or "Нет описания задания"
            files = item.get("files", [])
            files_count = len(files) if files else item.get("filesCount", 0)

            files_str = ""
            if files_count > 0:
                files_str = f" _\\(📎 {files_count} {format_file_plural(files_count)}\\)_"

            # Create expandable blockquote with **> and ||
            desc_escaped = esc_md(desc)
            lines = desc_escaped.split("\n")
            formatted_lines = [f"**>{lines[0]}"] + [f">{l}" for l in lines[1:]]
            quote_block = "\n".join(formatted_lines) + "||"

            res += f"📖 *{esc_md(name)}*{files_str}\n{quote_block}\n\n"
    else:
        res += "✨ _На этот день домашних заданий нет_"

    return res


def format_schedule_message(day_idx: int, lessons: List[Dict[str, Any]]) -> str:
    """Formats schedule with numbered badges, times and room indicators"""
    res = f"🗓 *{esc_md(WEEKDAYS[day_idx])}*\n\n"
    if day_idx == 6 or not lessons:
        res += "🛋 _В этот день уроков нет_"
        return res

    for idx, l in enumerate(lessons):
        num_str = l.get("num", str(idx + 1))
        name = l.get("name", "")
        room = l.get("room", "")

        bh, bm = l.get("beginHour"), l.get("beginMinute")
        eh, em = l.get("endHour"), l.get("endMinute")

        time_str = ""
        if bh is not None and bm is not None and eh is not None and em is not None:
            time_str = f"`{bh:02d}:{bm:02d}–{eh:02d}:{em:02d}` │ "

        emoji_num = NUM_EMOJIS[idx] if idx < len(NUM_EMOJIS) else f"`{num_str}`"
        room_str = f" • _каб\\. {esc_md(room)}_" if room else ""
        res += f"{emoji_num} {time_str}*{esc_md(name)}*{room_str}\n"

    return res


def format_period_grades_message(period_num: int, disciplines: List[Dict[str, Any]]) -> str:
    """Formats quarter grades with average calculation and badges"""
    res = f"📊 *Оценки за {period_num} четверть*\n\n"
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
        avg = round(float(d.get("average", 0.0) or 0.0), 2)
        avg_w = round(float(d.get("averagew", 0.0) or 0.0), 2)

        res += f"📖 *{esc_md(d.get('name', ''))}* • ср: *{esc_md(avg)}* _\\(взвеш: {esc_md(avg_w)}\\)_ \n"
        res += f"└ {grades_str}\n\n"

    if not has_grades:
        res += "✨ _Оценок за этот период пока нет_"

    return res


def format_week_grades_message(grades_dict: Dict[str, List[Any]]) -> str:
    """Formats weekly grades with subject groups and summary counts"""
    if not grades_dict:
        return "🗓 *Оценки на этой неделе*\n\n✨ _Оценок на этой неделе пока нет_"

    res = "🗓 *Оценки на этой неделе*\n\n"
    has_any = False

    for name, grades in grades_dict.items():
        if not grades:
            continue
        has_any = True
        formatted = []
        for g in grades:
            if isinstance(g, list):
                formatted.append(format_multi_grade(g))
            else:
                formatted.append(format_grade_badge(g))

        res += f"📖 *{esc_md(name)}*\n"
        res += f"└ {' • '.join(formatted)}\n\n"

    if not has_any:
        res += "✨ _Оценок на этой неделе пока нет_"

    return res


def format_year_grades_message(year_grades: List[Dict[str, Any]]) -> str:
    """Formats quarter and yearly final grades with structured column alignment"""
    if not year_grades:
        return "📑 *Четвертные и итоговые оценки*\n\n✨ _Четвертные оценки пока отсутствуют_"

    res = "📑 *Четвертные и итоговые оценки*\n\n"
    for item in year_grades:
        name = item.get("name", "")
        grades = item.get("grades", ["━", "━", "━", "━"])
        year_grade = item.get("yeargrade", "━")

        badges = [format_grade_badge(g) for g in grades]
        # Quarter markers I, II, III, IV
        q_str = f"I: {badges[0]} │ II: {badges[1]} │ III: {badges[2]} │ IV: {badges[3]}"
        res += f"📖 *{esc_md(name)}*\n"
        res += f"└ {q_str} ➔ *Итог:* {format_grade_badge(year_grade)}\n\n"

    return res


def format_calls_message() -> str:
    """Formats bell schedule with break durations"""
    return (
        "🔔 *Расписание звонков*\n\n"
        "1️⃣ │ `08:30 — 09:10`\n"
        "2️⃣ │ `09:20 — 10:00` _\\(перемена 20 мин\\)_\n"
        "3️⃣ │ `10:20 — 11:00` _\\(перемена 20 мин\\)_\n"
        "4️⃣ │ `11:20 — 12:00` _\\(перемена 20 мин\\)_\n"
        "5️⃣ │ `12:20 — 13:00`\n"
        "6️⃣ │ `13:10 — 13:50`\n"
        "7️⃣ │ `14:05 — 14:45`\n"
        "8️⃣ │ `14:55 — 15:35`"
    )


def format_help_message() -> str:
    """Formats structured help message with emojis and categories"""
    return (
        "🎓 *Телеграм\\-бот «Школьный дневник»*\n\n"
        "🛠 *Аккаунт и сервис*\n"
        "• /login — Подключение и вход через Дневник\n"
        "• /profile — Профиль ученика и школа\n"
        "• /help — Справка и команды\n"
        "• /delacc — Удалить аккаунт из бота\n\n"
        "📅 *Расписание*\n"
        "• /today — Расписание на сегодня\n"
        "• /nextday — Расписание на завтра\n"
        "• /all — Выбор любого дня недели\n"
        "• /calls — Расписание звонков\n\n"
        "📊 *Оценки*\n"
        "• /wgrades — Оценки на этой неделе\n"
        "• /pgrades — Четвертные и итоговые оценки\n"
        "• /grades — Меню выбора четверти\n\n"
        "✍️ *Домашнее задание*\n"
        "• /homework — Домашнее задание с перелистыванием дат"
    )
