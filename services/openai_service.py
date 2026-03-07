import whisper
import ollama
import json
import re
from datetime import datetime
import asyncio

# Загружаем Whisper модель один раз при старте
_whisper_model = None

def get_whisper_model():
    global _whisper_model
    if _whisper_model is None:
        print("Загружаю Whisper medium...")
        _whisper_model = whisper.load_model("medium")
        print("Whisper готов!")
    return _whisper_model


CLASSIFY_PROMPT = """
Ты — система классификации записей для личного помощника памяти.

Пользователь говорит или пишет что-то — твоя задача разобрать это и вернуть JSON.

Категории (выбирай ОДНУ, самую точную):
- task — нужно что-то сделать, купить, позвонить, вернуть, отправить. Если есть глагол действия — это task.
- idea — мысль, идея, что-то придумал, новая концепция
- note — наблюдение, факт, что-то интересное, просто запомнить
- state — как себя чувствует, настроение, самочувствие
- goal — цель на будущее, чего хочет достичь
- repeat — задача которую надо делать РЕГУЛЯРНО (каждый день, каждую неделю)
- question — хочет что-то выяснить, загуглить, спросить у кого-то
- chaos — совсем непонятно что имел в виду

ВАЖНО: «купить», «сделать», «позвонить», «вернуть», «убрать» — всегда task, не repeat!
repeat только если явно сказано «каждый день», «еженедельно», «регулярно».

Также определи:
- source: 'guest' если человек передаёт сообщение кому-то другому («скажи Антону», «передай что»), иначе 'owner'
- remind_at: если есть конкретное время или дата — верни в формате ISO 8601, иначе null
- has_explicit_time: true если время указано явно, false если нет

Верни ТОЛЬКО валидный JSON без markdown и пояснений:
{
  "category": "task",
  "summary": "краткое описание в 1 строку",
  "remind_at": null,
  "has_explicit_time": false,
  "source": "owner"
}
"""

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


async def transcribe(audio_path: str) -> str:
    """Расшифровка голосового через локальный Whisper (GPU)"""
    model = get_whisper_model()
    # Запускаем в executor чтобы не блокировать async loop
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(
        None,
        lambda: model.transcribe(audio_path, language="ru")
    )
    return result["text"].strip()


async def classify(text: str) -> dict:
    """Классификация текста через локальный Mistral (Ollama)"""
    for attempt in range(3):
        try:
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: ollama.chat(
                    model="mistral",
                    messages=[
                        {"role": "system", "content": CLASSIFY_PROMPT},
                        {"role": "user", "content": text}
                    ],
                    options={"temperature": 0}
                )
            )
            raw = response["message"]["content"].strip()
            raw = re.sub(r"```json|```", "", raw).strip()
            return json.loads(raw)
        except Exception as e:
            print(f"Ошибка classify (попытка {attempt + 1}): {e}")
            if attempt == 2:
                return {
                    "category": "chaos",
                    "summary": text[:100],
                    "remind_at": None,
                    "has_explicit_time": False,
                    "source": "owner"
                }


async def parse_time(text: str) -> datetime | None:
    """Парсинг времени — сначала простые паттерны в коде, потом Mistral"""
    import pytz
    from datetime import timedelta
    moscow_tz = pytz.timezone("Europe/Moscow")
    now = datetime.now(moscow_tz)
    t = text.strip().lower()

    # ── Простые паттерны считаем сами ──────────────────────────────
    # «через X минут»
    m = re.search(r"через\s+(\d+)\s+мин", t)
    if m:
        return now + timedelta(minutes=int(m.group(1)))

    # «через X час»
    m = re.search(r"через\s+(\d+)\s+час", t)
    if m:
        return now + timedelta(hours=int(m.group(1)))

    # «через X дн» / «через X день» / «через X дней»
    m = re.search(r"через\s+(\d+)\s+д", t)
    if m:
        return now + timedelta(days=int(m.group(1)))

    # «в ЧЧ:ММ»
    m = re.search(r"в\s+(\d{1,2}):(\d{2})", t)
    if m:
        result = now.replace(hour=int(m.group(1)), minute=int(m.group(2)), second=0, microsecond=0)
        if result < now:
            result += timedelta(days=1)
        return result

    # «в ЧЧ» (без минут)
    m = re.search(r"в\s+(\d{1,2})($|\s)", t)
    if m:
        result = now.replace(hour=int(m.group(1)), minute=0, second=0, microsecond=0)
        if result < now:
            result += timedelta(days=1)
        return result

    # «завтра в ЧЧ:ММ»
    m = re.search(r"завтра.*?(\d{1,2}):(\d{2})", t)
    if m:
        tomorrow = now + timedelta(days=1)
        return tomorrow.replace(hour=int(m.group(1)), minute=int(m.group(2)), second=0, microsecond=0)

    # «завтра в ЧЧ»
    m = re.search(r"завтра.*?(\d{1,2})", t)
    if m:
        tomorrow = now + timedelta(days=1)
        return tomorrow.replace(hour=int(m.group(1)), minute=0, second=0, microsecond=0)

    # «завтра» без времени — утром в 9:00
    if "завтра" in t:
        tomorrow = now + timedelta(days=1)
        return tomorrow.replace(hour=9, minute=0, second=0, microsecond=0)

    # ── Сложные случаи — отдаём Mistral ────────────────────────────
    try:
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: ollama.chat(
                model="mistral",
                messages=[
                    {"role": "system", "content": f"""Сейчас по московскому времени: {now.strftime('%Y-%m-%d %H:%M')} (UTC+3).
Пользователь написал время в свободной форме.
Вычисли точное московское время и верни ТОЛЬКО в формате ISO 8601 (например 2026-03-08T23:19:00).
Ничего кроме даты. Если не можешь — верни null."""},
                    {"role": "user", "content": text}
                ],
                options={"temperature": 0}
            )
        )
        raw = response["message"]["content"].strip()
        if "null" in raw.lower():
            return None
        match = re.search(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}", raw)
        if match:
            naive_dt = datetime.fromisoformat(match.group())
            return moscow_tz.localize(naive_dt)
        return None
    except Exception as e:
        print(f"Ошибка parse_time: {e}")
        return None
