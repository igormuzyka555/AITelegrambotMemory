from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
from database.crud import get_open_tasks, get_entries_by_date
from datetime import datetime, timedelta
import pytz

router = Router()

MOSCOW_TZ = pytz.timezone("Europe/Moscow")

CATEGORY_EMOJI = {
    "task": "✅",
    "idea": "💡",
    "note": "📝",
    "state": "😌",
    "goal": "🎯",
    "repeat": "🔁",
    "question": "❓",
    "chaos": "🌀"
}

CATEGORY_NAME = {
    "task": "Задачи",
    "idea": "Идеи",
    "note": "Заметки",
    "state": "Состояние",
    "goal": "Цели",
    "repeat": "Повторяющиеся",
    "question": "Вопросы",
    "chaos": "Разное"
}


# ── /tasks — все незакрытые задачи ───────────────────────────────────────
@router.message(Command("tasks"))
async def cmd_tasks(message: Message):
    tasks = get_open_tasks(message.from_user.id)

    if not tasks:
        await message.answer("🎉 Все задачи выполнены! Незакрытых нет.")
        return

    builder = InlineKeyboardBuilder()
    lines = [f"📌 Незакрытые задачи ({len(tasks)}):\n"]

    for i, task in enumerate(tasks, 1):
        date_str = task.created_at.strftime("%d.%m")
        lines.append(f"{i}. {task.summary} ({date_str})")
        short = task.summary[:20] + "…" if len(task.summary) > 20 else task.summary
        builder.button(text=f"✅ {short}", callback_data=f"done_{task.id}")

    builder.adjust(1)

    await message.answer(
        "\n".join(lines),
        reply_markup=builder.as_markup()
    )


# ── /ideas — идеи за последние 7 дней ────────────────────────────────────
@router.message(Command("ideas"))
async def cmd_ideas(message: Message):
    now = datetime.now(MOSCOW_TZ)
    ideas = []

    for i in range(7):
        day = now - timedelta(days=i)
        date_str = day.strftime("%Y-%m-%d")
        entries = get_entries_by_date(message.from_user.id, date_str)
        ideas.extend([e for e in entries if e.category == "idea"])

    if not ideas:
        await message.answer("💡 Идей за последние 7 дней нет.")
        return

    lines = [f"💡 Идеи за 7 дней ({len(ideas)}):\n"]
    for idea in ideas:
        date_str = idea.created_at.strftime("%d.%m")
        lines.append(f"• {idea.summary} ({date_str})")

    await message.answer("\n".join(lines))


# ── /today — все записи за сегодня ───────────────────────────────────────
@router.message(Command("today"))
async def cmd_today(message: Message):
    now = datetime.now(MOSCOW_TZ)
    today_str = now.strftime("%Y-%m-%d")
    entries = get_entries_by_date(message.from_user.id, today_str)

    if not entries:
        await message.answer("📭 Сегодня записей нет.")
        return

    by_category = {}
    for entry in entries:
        cat = entry.category or "chaos"
        if cat not in by_category:
            by_category[cat] = []
        by_category[cat].append(entry)

    lines = [f"📅 Сегодня, {now.strftime('%d.%m')} — {len(entries)} записей:\n"]

    for cat in ["task", "idea", "note", "goal", "state", "repeat", "question", "chaos"]:
        if cat not in by_category:
            continue
        emoji = CATEGORY_EMOJI.get(cat, "📝")
        name = CATEGORY_NAME.get(cat, cat)
        lines.append(f"{emoji} {name}:")
        for e in by_category[cat]:
            status = " ✓" if e.is_done else ""
            guest = f" (от {e.guest_name})" if e.source == "guest" else ""
            lines.append(f"  • {e.summary}{status}{guest}")
        lines.append("")

    await message.answer("\n".join(lines))


# ── /memory — вся информация о пользователе ─────────────────────────────
@router.message(Command("memory"))
async def cmd_memory(message: Message):
    now = datetime.now(MOSCOW_TZ)

    all_entries = []
    for i in range(30):
        day = now - timedelta(days=i)
        date_str = day.strftime("%Y-%m-%d")
        entries = get_entries_by_date(message.from_user.id, date_str)
        all_entries.extend(entries)

    if not all_entries:
        await message.answer("🧠 Пока ничего не записано.")
        return

    open_tasks = [e for e in all_entries if e.category == "task" and not e.is_done and not e.archived_at and e.source == "owner"]
    ideas = [e for e in all_entries if e.category == "idea"]
    notes = [e for e in all_entries if e.category == "note"]
    goals = [e for e in all_entries if e.category == "goal"]
    states = [e for e in all_entries if e.category == "state"]
    questions = [e for e in all_entries if e.category == "question"]

    lines = ["🧠 Всё что я знаю о тебе:\n"]

    if open_tasks:
        lines.append(f"📌 Незакрытые задачи ({len(open_tasks)}):")
        for e in open_tasks:
            lines.append(f"  • {e.summary}")
        lines.append("")

    if goals:
        lines.append(f"🎯 Цели ({len(goals)}):")
        for e in goals:
            lines.append(f"  • {e.summary}")
        lines.append("")

    if ideas:
        lines.append(f"💡 Идеи ({len(ideas)}):")
        for e in ideas:
            lines.append(f"  • {e.summary}")
        lines.append("")

    if notes:
        lines.append(f"📝 Заметки ({len(notes)}):")
        for e in notes:
            lines.append(f"  • {e.raw_text}")
        lines.append("")

    if questions:
        lines.append(f"❓ Вопросы ({len(questions)}):")
        for e in questions:
            lines.append(f"  • {e.summary}")
        lines.append("")

    if states:
        lines.append(f"😌 Состояния ({len(states)}):")
        for e in states:
            date_str = e.created_at.strftime("%d.%m")
            lines.append(f"  • {e.summary} ({date_str})")
        lines.append("")

    await message.answer("\n".join(lines))


# ── /notes — все заметки за 7 дней ─────────────────────────────────────
@router.message(Command("notes"))
async def cmd_notes(message: Message):
    now = datetime.now(MOSCOW_TZ)
    notes = []

    for i in range(7):
        day = now - timedelta(days=i)
        date_str = day.strftime("%Y-%m-%d")
        entries = get_entries_by_date(message.from_user.id, date_str)
        notes.extend([e for e in entries if e.category == "note"])

    if not notes:
        await message.answer("📝 Заметок за последние 7 дней нет.")
        return

    lines = [f"📝 Заметки за 7 дней ({len(notes)}):\n"]
    current_date = None

    for note in notes:
        note_date = note.created_at.strftime("%d.%m")
        if note_date != current_date:
            current_date = note_date
            lines.append(f"\n— {note_date} —")
        lines.append(f"• {note.raw_text}")

    await message.answer("\n".join(lines))


# ── /week — сводка за 7 дней ─────────────────────────────────────────────
@router.message(Command("week"))
async def cmd_week(message: Message):
    now = datetime.now(MOSCOW_TZ)
    all_entries = []

    for i in range(7):
        day = now - timedelta(days=i)
        date_str = day.strftime("%Y-%m-%d")
        entries = get_entries_by_date(message.from_user.id, date_str)
        all_entries.extend(entries)

    if not all_entries:
        await message.answer("📭 За последние 7 дней записей нет.")
        return

    total = len(all_entries)
    done = len([e for e in all_entries if e.is_done])
    open_tasks = len([e for e in all_entries if e.category == "task" and not e.is_done and not e.archived_at])
    guest_count = len([e for e in all_entries if e.source == "guest"])

    cat_count = {}
    for e in all_entries:
        cat = e.category or "chaos"
        cat_count[cat] = cat_count.get(cat, 0) + 1

    lines = [
        f"📊 Итоги недели ({(now - timedelta(days=6)).strftime('%d.%m')} — {now.strftime('%d.%m')}):\n",
        f"📝 Всего записей: {total}",
        f"✅ Выполнено задач: {done}",
        f"📌 Незакрытых задач: {open_tasks}",
        f"📩 Сообщений от других: {guest_count}",
        "",
        "По категориям:"
    ]

    for cat, count in sorted(cat_count.items(), key=lambda x: x[1], reverse=True):
        emoji = CATEGORY_EMOJI.get(cat, "📝")
        name = CATEGORY_NAME.get(cat, cat)
        lines.append(f"  {emoji} {name}: {count}")

    await message.answer("\n".join(lines))
