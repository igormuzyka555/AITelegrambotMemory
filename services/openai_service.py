from openai import AsyncOpenAI
from dotenv import load_dotenv
import os
import json
import re
from datetime import datetime

load_dotenv()

client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

CLASSIFY_PROMPT = """
Ты — система классификации записей для личного помощника памяти.

Пользователь говорит или пишет что-то — твоя задача разобрать это и вернуть JSON.

Категории:
- task — задача, что-то нужно сделать
- idea — идея, мысль о проекте или жизни
- note — заметка, наблюдение, факт
- state — состояние, как себя чувствует
- goal — цель, чего хочет достичь
- repeat — повторяющаяся задача
- question — что хочет выяснить или спросить
- chaos — непонятно что

Также определи:
- source: 'guest' если человек явно передаёт сообщение кому-то другому (например «скажи Антону», «передай что»), иначе 'owner'
- remind_at: если в тексте есть конкретное время или дата — верни в формате ISO 8601, иначе null
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
    """Расшифровка голосового через Whisper"""
    with open(audio_path, "rb") as audio_file:
        response = await client.audio.transcriptions.create(
            model="whisper-1",
            file=audio_file
        )
    return response.text


async def classify(text: str) -> dict:
    """Классификация текста через GPT-4o"""
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
            # Убираем markdown если вдруг появился
            raw = re.sub(r"```json|```", "", raw).strip()
            return json.loads(raw)
        except Exception as e:
            if attempt == 2:
                # Если все попытки провалились — возвращаем базовый результат
                return {
                    "category": "chaos",
                    "summary": text[:100],
                    "remind_at": None,
                    "has_explicit_time": False,
                    "source": "owner"
                }



async def parse_time(text: str) -> datetime | None:
    """Парсинг свободного текста времени через GPT-4o"""
    from datetime import datetime
    now = datetime.utcnow()

    try:
        response = await client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": f"""
Сейчас: {now.strftime('%Y-%m-%d %H:%M')} UTC.
Пользователь написал время в свободной форме.
Переведи в формат ISO 8601 (например 2026-02-25T15:30:00).
Верни ТОЛЬКО дату и время в формате ISO 8601, ничего больше.
Если не можешь определить — верни null.
"""},
                {"role": "user", "content": text}
            ],
            temperature=0
        )
        raw = response.choices[0].message.content.strip()
        if raw == "null":
            return None
        return datetime.fromisoformat(raw)
    except Exception:
        return None
