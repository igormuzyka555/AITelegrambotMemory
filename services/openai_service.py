import json
import re
import os
import asyncio
import logging
import time
from datetime import datetime, timedelta
import pytz
from dotenv import load_dotenv

load_dotenv()

# ── ЛОГИРОВАНИЕ ───────────────────────────────────────────────────────────
logger = logging.getLogger(__name__)
# ─────────────────────────────────────────────────────────────────────────

# ── Режим работы: local или openai ───────────────────────────────────────
AI_MODE = os.getenv("AI_MODE", "local").lower()
logger.info(f"AI режим: {AI_MODE.upper()}")

MOSCOW_TZ = pytz.timezone("Europe/Moscow")

_whisper_model = None
_openai_client = None


def get_whisper_model():
    global _whisper_model
    if _whisper_model is None:
        import whisper
        logger.info("Загружаю Whisper medium...")
        _whisper_model = whisper.load_model("medium")
        logger.info("Whisper готов!")
    return _whisper_model


def get_openai_client():
    global _openai_client
    if _openai_client is None:
        from openai import AsyncOpenAI
        _openai_client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    return _openai_client


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


# ── ТРАНСКРИПЦИЯ ─────────────────────────────────────────────────────────

async def transcribe(audio_path: str) -> str:
    start = time.time()
    logger.info(f"transcribe START | режим={AI_MODE}")
    try:
        if AI_MODE == "openai":
            result = await _transcribe_openai(audio_path)
        else:
            result = await _transcribe_local(audio_path)
        elapsed = round(time.time() - start, 2)
        logger.info(f"transcribe END | время={elapsed}с | символов={len(result)}")
        return result
    except Exception as e:
        logger.error(f"transcribe ERROR | {e}")
        raise


async def _transcribe_local(audio_path: str) -> str:
    model = get_whisper_model()
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(
        None,
        lambda: model.transcribe(audio_path, language="ru")
    )
    return result["text"].strip()


async def _transcribe_openai(audio_path: str) -> str:
    client = get_openai_client()
    with open(audio_path, "rb") as f:
        result = await client.audio.transcriptions.create(
            model="whisper-1",
            file=f,
            language="ru"
        )
    return result.text.strip()


# ── КЛАССИФИКАЦИЯ ────────────────────────────────────────────────────────

async def classify(text: str) -> dict:
    start = time.time()
    logger.info(f"classify START | режим={AI_MODE} | текст={text[:60]}")
    try:
        if AI_MODE == "openai":
            result = await _classify_openai(text)
        else:
            result = await _classify_local(text)
        elapsed = round(time.time() - start, 2)
        logger.info(f"classify END | категория={result.get('category')} | время={elapsed}с")
        return result
    except Exception as e:
        logger.error(f"classify ERROR | {e}")
        return _fallback(text)


async def _classify_local(text: str) -> dict:
    import ollama
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
            logger.warning(f"classify local попытка {attempt + 1}/3 | ошибка: {e}")
            if attempt == 2:
                return _fallback(text)


async def _classify_openai(text: str) -> dict:
    client = get_openai_client()
    for attempt in range(3):
        try:
            response = await client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": CLASSIFY_PROMPT},
                    {"role": "user", "content": text}
                ],
                temperature=0
            )
            raw = response.choices[0].message.content.strip()
            raw = re.sub(r"```json|```", "", raw).strip()
            return json.loads(raw)
        except Exception as e:
            logger.warning(f"classify openai попытка {attempt + 1}/3 | ошибка: {e}")
            if attempt == 2:
                return _fallback(text)


def _fallback(text: str) -> dict:
    logger.warning(f"classify FALLBACK | текст={text[:60]}")
    return {
        "category": "chaos",
        "summary": text[:100],
        "remind_at": None,
        "has_explicit_time": False,
        "source": "owner"
    }


# ── ПАРСИНГ ВРЕМЕНИ ───────────────────────────────────────────────────────

async def parse_time(text: str) -> datetime | None:
    logger.info(f"parse_time START | текст={text[:60]}")
    now = datetime.now(MOSCOW_TZ)
    t = text.strip().lower()

    # «через X минут»
    m = re.search(r"через\s+(\d+)\s+мин", t)
    if m:
        result = now + timedelta(minutes=int(m.group(1)))
        logger.info(f"parse_time END | результат={result} | паттерн=через_минут")
        return result

    # «через X час»
    m = re.search(r"через\s+(\d+)\s+час", t)
    if m:
        result = now + timedelta(hours=int(m.group(1)))
        logger.info(f"parse_time END | результат={result} | паттерн=через_часов")
        return result

    # «через X дней/день/дня»
    m = re.search(r"через\s+(\d+)\s+д", t)
    if m:
        result = now + timedelta(days=int(m.group(1)))
        logger.info(f"parse_time END | результат={result} | паттерн=через_дней")
        return result

    # «в ЧЧ:ММ»
    m = re.search(r"в\s+(\d{1,2}):(\d{2})", t)
    if m:
        result = now.replace(hour=int(m.group(1)), minute=int(m.group(2)), second=0, microsecond=0)
        if result < now:
            result += timedelta(days=1)
        logger.info(f"parse_time END | результат={result} | паттерн=в_ЧЧ:ММ")
        return result

    # «в ЧЧ»
    m = re.search(r"в\s+(\d{1,2})($|\s)", t)
    if m:
        result = now.replace(hour=int(m.group(1)), minute=0, second=0, microsecond=0)
        if result < now:
            result += timedelta(days=1)
        logger.info(f"parse_time END | результат={result} | паттерн=в_ЧЧ")
        return result

    # «завтра в ЧЧ:ММ»
    m = re.search(r"завтра.*?(\d{1,2}):(\d{2})", t)
    if m:
        tomorrow = now + timedelta(days=1)
        result = tomorrow.replace(hour=int(m.group(1)), minute=int(m.group(2)), second=0, microsecond=0)
        logger.info(f"parse_time END | результат={result} | паттерн=завтра_ЧЧ:ММ")
        return result

    # «завтра в ЧЧ»
    m = re.search(r"завтра.*?(\d{1,2})", t)
    if m:
        tomorrow = now + timedelta(days=1)
        result = tomorrow.replace(hour=int(m.group(1)), minute=0, second=0, microsecond=0)
        logger.info(f"parse_time END | результат={result} | паттерн=завтра_ЧЧ")
        return result

    # «завтра» без времени
    if "завтра" in t:
        tomorrow = now + timedelta(days=1)
        result = tomorrow.replace(hour=9, minute=0, second=0, microsecond=0)
        logger.info(f"parse_time END | результат={result} | паттерн=завтра")
        return result

    # Сложные случаи — отдаём AI
    logger.info("parse_time | паттерн не найден, отправляю в AI")
    if AI_MODE == "openai":
        return await _parse_time_openai(text, now)
    return await _parse_time_local(text, now)


async def _parse_time_local(text: str, now: datetime) -> datetime | None:
    import ollama
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
            logger.info("parse_time local | AI вернул null")
            return None
        match = re.search(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}", raw)
        if match:
            result = MOSCOW_TZ.localize(datetime.fromisoformat(match.group()))
            logger.info(f"parse_time local END | результат={result}")
            return result
    except Exception as e:
        logger.error(f"parse_time local ERROR | {e}")
    return None


async def _parse_time_openai(text: str, now: datetime) -> datetime | None:
    client = get_openai_client()
    try:
        response = await client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": f"""Сейчас по московскому времени: {now.strftime('%Y-%m-%d %H:%M')} (UTC+3).
Пользователь написал время в свободной форме.
Вычисли точное московское время и верни ТОЛЬКО в формате ISO 8601 (например 2026-03-08T23:19:00).
Ничего кроме даты. Если не можешь — верни null."""},
                {"role": "user", "content": text}
            ],
            temperature=0
        )
        raw = response.choices[0].message.content.strip()
        if "null" in raw.lower():
            logger.info("parse_time openai | AI вернул null")
            return None
        match = re.search(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}", raw)
        if match:
            result = MOSCOW_TZ.localize(datetime.fromisoformat(match.group()))
            logger.info(f"parse_time openai END | результат={result}")
            return result
    except Exception as e:
        logger.error(f"parse_time openai ERROR | {e}")
    return None
