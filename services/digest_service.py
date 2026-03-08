from aiogram import Bot
from aiogram.utils.keyboard import InlineKeyboardBuilder
from database.crud import get_entries_by_date, save_digest, get_all_owner_users
from datetime import datetime
import pytz
import json

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


async def generate_digest(bot: Bot, user_id: int, first_name: str):
    """Генерация и отправка вечерней сводки пользователю"""
    now = datetime.now(MOSCOW_TZ)
    today_str = now.strftime("%Y-%m-%d")

    # Получаем все записи за сегодня
    entries = get_entries_by_date(user_id, today_str)

    # Пустой день
    if not entries:
        await bot.send_message(
            user_id,
            "🌙 Сегодня тишина.\nЗавтра новый день. 💫"
        )
        save_digest(user_id, today_str, json.dumps({"empty": True}))
        return

    # Разбиваем по категориям
    done_tasks = [e for e in entries if e.category == "task" and e.is_done and e.source == "owner"]
    open_tasks = [e for e in entries if e.category == "task" and not e.is_done and not e.archived_at and e.source == "owner"]
    ideas = [e for e in entries if e.category == "idea"]
    notes = [e for e in entries if e.category == "note"]
    states = [e for e in entries if e.category == "state"]
    goals = [e for e in entries if e.category == "goal"]
    guest_tasks = [e for e in entries if e.source == "guest"]

    # Строим текст сводки
    lines = [f"🌙 *Сводка за {now.strftime('%d.%m.%Y')}*, {first_name}\n"]

    if done_tasks:
        lines.append("*✅ Сделано:*")
        for e in done_tasks:
            lines.append(f"  • {e.summary}")
        lines.append("")

    if open_tasks:
        lines.append("*📌 Незакрытые задачи:*")
        for e in open_tasks:
            lines.append(f"  • {e.summary}")
        lines.append("")

    if ideas:
        lines.append("*💡 Идеи:*")
        for e in ideas:
            lines.append(f"  • {e.summary}")
        lines.append("")

    if notes:
        lines.append("*📝 Заметки:*")
        for e in notes:
            lines.append(f"  • {e.summary}")
        lines.append("")

    if goals:
        lines.append("*🎯 Цели:*")
        for e in goals:
            lines.append(f"  • {e.summary}")
        lines.append("")

    if states:
        lines.append("*😌 Состояние:*")
        for e in states:
            lines.append(f"  • {e.summary}")
        lines.append("")

    if guest_tasks:
        lines.append("*📩 Сообщения от других:*")
        for e in guest_tasks:
            name = e.guest_name or "Гость"
            status = "✅" if e.is_done else "⏳"
            lines.append(f"  {status} от {name}: {e.summary}")
        lines.append("")

    # Финальная строка
    total = len(entries)
    done_count = len(done_tasks)
    lines.append(f"_Всего записей за день: {total}. Выполнено задач: {done_count}._")

    text = "\n".join(lines)

    # Кнопки [Сделал] для незакрытых задач
    if open_tasks:
        builder = InlineKeyboardBuilder()
        for e in open_tasks:
            short = e.summary[:25] + "…" if len(e.summary) > 25 else e.summary
            builder.button(text=f"✅ {short}", callback_data=f"done_{e.id}")
        builder.adjust(1)

        await bot.send_message(
            user_id,
            text,
            parse_mode="Markdown",
            reply_markup=builder.as_markup()
        )
    else:
        await bot.send_message(user_id, text, parse_mode="Markdown")

    # Сохраняем сводку в БД
    content = {
        "date": today_str,
        "total": total,
        "done": done_count,
        "open": len(open_tasks),
        "ideas": len(ideas),
        "notes": len(notes),
        "guest": len(guest_tasks)
    }
    save_digest(user_id, today_str, json.dumps(content, ensure_ascii=False))
    print(f"Сводка отправлена пользователю {user_id}")
