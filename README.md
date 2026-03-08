# 🧠 Второй Мозг — Telegram Bot v1.0.0



Персональный AI-ассистент памяти для людей с ADHD и не только.  
Записывает голосовые и текстовые заметки, классифицирует их, напоминает и присылает вечернюю сводку.

---

## 📋 Содержание

- [Что умеет бот](#что-умеет-бот)
- [Архитектура](#архитектура)
- [Структура проекта](#структура-проекта)
- [База данных](#база-данных)
- [Требования](#требования)
- [Быстрый старт](#быстрый-старт)
- [Запуск на локальных моделях](#запуск-на-локальных-моделях-whisper--ollama)
- [Запуск на OpenAI](#запуск-на-openai)
- [Команды бота](#команды-бота)
- [Веб-аналитика](#веб-аналитика)
- [Переменные окружения](#переменные-окружения)
- [Монетизация](#монетизация)

---

## Что умеет бот

### 🎙️ Захват записей
- Принимает **голосовые сообщения** — расшифровывает через Whisper
- Принимает **текстовые сообщения** — любой формат, свободный текст
- Автоматически классифицирует по 8 категориям через AI

### 📌 8 категорий записей
| Категория | Эмодзи | Описание |
|-----------|--------|----------|
| task | ✅ | Задача — что-то нужно сделать |
| idea | 💡 | Идея, мысль, концепция |
| note | 📝 | Заметка, факт, наблюдение |
| state | 😌 | Настроение, самочувствие |
| goal | 🎯 | Цель на будущее |
| repeat | 🔁 | Регулярная задача |
| question | ❓ | Вопрос, нужно выяснить |
| chaos | 🌀 | Непонятно что |

### ⏰ Умные напоминания
- При записи задачи бот спрашивает когда напомнить
- Кнопки: 30 минут / 1 час / 2 часа / Вечером / Завтра утром / Своё время
- Своё время парсится через regex + Mistral (локально) или GPT (OpenAI)
- Если задача не выполнена — напоминает каждый день
- С 7-го напоминания появляется кнопка «Архивировать»

### 🤝 Режим гостя (партнёра)
- Любой человек может открыть бота и отправить задачу владельцу
- При `/start` выбор роли: Пользователь или Партнёр
- Партнёр пишет `/guest` → указывает username владельца → пишет сообщение и комментарий → выбирает время
- Когда владелец выполняет задачу — партнёру приходит уведомление

### 🌙 Вечерняя сводка
- Каждый день в выбранное время приходит сводка дня
- Блоки: сделано / незакрытые / идеи / заметки / состояние / от других
- Кнопки [✅ Сделал] прямо в сводке для незакрытых задач
- Если записей нет — «Сегодня тишина. Завтра новый день.»

### 📊 Команды просмотра
- `/tasks` — все незакрытые задачи с кнопками
- `/today` — записи за сегодня по категориям
- `/ideas` — идеи за 7 дней
- `/notes` — заметки за 7 дней с полным текстом
- `/week` — статистика за неделю
- `/memory` — всё что бот знает о тебе за 30 дней
- `/digest` — вечерняя сводка вручную

---

## Архитектура

```
Telegram ←→ aiogram 3 ←→ Handlers
                              ↓
                         Services
                    ┌─────────────────┐
                    │  openai_service  │  ← Whisper + Mistral (или OpenAI)
                    │  scheduler       │  ← APScheduler
                    │  reminder_service│  ← Логика напоминаний
                    │  digest_service  │  ← Генерация сводки
                    └─────────────────┘
                              ↓
                         PostgreSQL
                              ↓
                    analytics_web (FastAPI)
```

---

## Структура проекта

```
Telegram/
├── main.py                          # Точка входа, запуск бота
├── .env                             # Секреты (не в git)
├── .gitignore
│
├── bot/
│   ├── handlers/
│   │   ├── onboarding.py            # /start, выбор роли, онбординг
│   │   ├── capture.py               # Захват текста и голоса
│   │   ├── recall.py                # Кнопки: Сделал / Снуз / Архив
│   │   ├── guest.py                 # Режим партнёра (/guest)
│   │   ├── digest.py                # /digest команда
│   │   └── views.py                 # /tasks /today /ideas /notes /week /memory
│   ├── middlewares/
│   │   └── subscription.py          # Проверка подписки (временно отключена)
│   └── keyboards/
│       └── inline.py
│
├── database/
│   ├── models.py                    # SQLAlchemy модели: User, Entry, Digest, Analytics
│   └── crud.py                      # Все операции с БД
│
├── services/
│   ├── openai_service.py            # AI: транскрипция + классификация + парсинг времени
│   ├── scheduler.py                 # APScheduler: напоминания + сводки
│   ├── reminder_service.py          # Логика отправки напоминаний
│   └── digest_service.py            # Генерация вечерней сводки
│
└── analytics_web/
    ├── main.py                      # FastAPI дашборд аналитики
    └── templates/
        ├── login.html               # Страница входа
        └── dashboard.html           # Дашборд с графиками
```

---

## База данных

### Таблица `users`
| Поле | Тип | Описание |
|------|-----|----------|
| user_id | BIGINT PK | Telegram ID |
| username | VARCHAR | @username (lowercase) |
| first_name | VARCHAR | Имя из Telegram |
| role | VARCHAR | owner / guest |
| digest_time | VARCHAR | Время сводки (HH:MM) |
| is_onboarded | BOOLEAN | Прошёл онбординг |
| is_subscribed | BOOLEAN | Активная подписка |
| trial_start | DATETIME | Начало триала |
| subscription_end | DATETIME | Конец подписки |

### Таблица `entries`
| Поле | Тип | Описание |
|------|-----|----------|
| id | INT PK | Автоинкремент |
| user_id | BIGINT | Владелец записи |
| source | VARCHAR | owner / guest |
| guest_name | VARCHAR | Имя гостя |
| guest_telegram_id | BIGINT | ID гостя для уведомления |
| raw_text | TEXT | Оригинальный текст |
| transcription | TEXT | Расшифровка голоса |
| category | VARCHAR | Категория (8 штук) |
| summary | TEXT | Краткое описание от AI |
| remind_at | DATETIME | Время напоминания |
| remind_count | INT | Счётчик напоминаний |
| is_done | BOOLEAN | Выполнена |
| archived_at | DATETIME | Дата архивации |

---

## Требования

- Python 3.10+
- PostgreSQL 14+
- ffmpeg (для обработки голосовых)

### Для локальных моделей (без OpenAI):
- RAM: минимум 8GB (рекомендуется 16GB)
- GPU: опционально (RTX 3060+ для ускорения Whisper)
- Ollama
- Whisper medium (~1.5GB)
- Mistral через Ollama (~4.7GB)

### Для OpenAI:
- API ключ OpenAI с балансом
- Модели: gpt-4o + whisper-1

---

## Быстрый старт

### 1. Клонируй репозиторий
```bash
git clone https://github.com/ТВО_USERNAME/second-brain-bot.git
cd second-brain-bot
```

### 2. Установи зависимости
```bash
python -m pip install aiogram apscheduler sqlalchemy psycopg2-binary python-dotenv pytz fastapi uvicorn jinja2 httpx
```

### 3. Создай базу данных PostgreSQL
```sql
CREATE DATABASE secondbrain;
```

### 4. Создай `.env` файл
```env
BOT_TOKEN=твой_токен_от_BotFather
DATABASE_URL=postgresql://postgres:пароль@localhost:5432/secondbrain
OWNER_CHAT_ID=твой_telegram_id
ANALYTICS_PASSWORD=твой_пароль_для_дашборда
OPENAI_API_KEY=           # оставь пустым если используешь локальные модели
PAYMENT_TOKEN=            # токен ЮКасса (опционально)
WEBHOOK_URL=              # для деплоя (опционально)
```

### 5. Установи ffmpeg
**Windows:**
```bash
winget install --id Gyan.FFmpeg
```
Перезапусти терминал после установки.

**Linux/Mac:**
```bash
sudo apt install ffmpeg      # Ubuntu/Debian
brew install ffmpeg          # macOS
```

### 6. Запусти бота
```bash
python main.py
```

---

## Запуск на локальных моделях (Whisper + Ollama)

Этот режим работает **без интернета и без OpenAI API**. Весь AI запускается на твоём компьютере.

### Шаг 1 — Установи Whisper
```bash
python -m pip install openai-whisper
```

При первом запуске бот автоматически скачает модель `medium` (~1.5GB).  
Для слабых компьютеров можно использовать модель `small` — измени в `services/openai_service.py`:
```python
_whisper_model = whisper.load_model("small")   # быстрее, менее точно
_whisper_model = whisper.load_model("medium")  # баланс (по умолчанию)
_whisper_model = whisper.load_model("large")   # точнее, нужно 16GB RAM
```

### Шаг 2 — Установи Ollama
Скачай с **ollama.com** и установи.

Затем скачай модель Mistral:
```bash
ollama pull mistral
```

Запусти Ollama (должен работать в фоне):
```bash
ollama serve
```

### Шаг 3 — Убедись что в `services/openai_service.py` используется локальный режим

Файл уже настроен на локальные модели по умолчанию:
```python
import whisper
import ollama

# Транскрипция через локальный Whisper
async def transcribe(audio_path):
    model = get_whisper_model()
    result = model.transcribe(audio_path, language="ru")
    return result["text"]

# Классификация через локальный Mistral
async def classify(text):
    response = ollama.chat(model="mistral", messages=[...])
    ...
```

### Производительность на разных конфигурациях
| Железо | Whisper | Классификация |
|--------|---------|---------------|
| CPU только | ~15-30 сек на сообщение | ~5-10 сек |
| RTX 3060 6GB | ~2-5 сек | ~2-3 сек |
| RTX 4050 6GB | ~2-4 сек | ~2-3 сек |
| RTX 4090 | <1 сек | <1 сек |
---

## Команды бота

| Команда | Описание |
|---------|----------|
| `/start` | Главное меню / онбординг |
| `/tasks` | Все незакрытые задачи |
| `/today` | Записи за сегодня |
| `/week` | Итоги за неделю |
| `/ideas` | Идеи за 7 дней |
| `/notes` | Заметки за 7 дней |
| `/memory` | Всё что бот знает о тебе |
| `/digest` | Вечерняя сводка вручную |
| `/guest` | Отправить задачу партнёру |

---

## Веб-аналитика

FastAPI дашборд с метриками и графиками.

### Запуск
```bash
python -m uvicorn analytics_web.main:app --host 127.0.0.1 --port 8000 --reload
```

Открой **http://127.0.0.1:8000** и введи пароль из `.env` (`ANALYTICS_PASSWORD`).

### Метрики на дашборде
- Всего пользователей / активных за 7 дней
- Платящих пользователей / конверсия триал → платный
- Всего записей / выполненных задач / незакрытых
- Зомби-задачи (3+ напоминания, не выполнены)
- Гостевые записи
- Графики: категории / новые пользователи / записи по дням
- Таблица всех пользователей

---

## Переменные окружения

| Переменная | Обязательна | Описание |
|------------|-------------|----------|
| `BOT_TOKEN` | ✅ | Токен бота от @BotFather |
| `DATABASE_URL` | ✅ | postgresql://user:pass@host:port/db |
| `OWNER_CHAT_ID` | ✅ | Твой Telegram ID |
| `ANALYTICS_PASSWORD` | ✅ | Пароль для дашборда |
| `OPENAI_API_KEY` | ❌ | Нужен только для режима OpenAI |
| `PAYMENT_TOKEN` | ❌ | Токен ЮКасса для приёма оплаты |
| `WEBHOOK_URL` | ❌ | URL для деплоя на сервер |

## Технологии

| Стек | Версия |
|------|--------|
| Python | 3.10+ |
| aiogram | 3.x |
| SQLAlchemy | 2.x |
| PostgreSQL | 14+ |
| APScheduler | 3.x |
| FastAPI | 0.x |
| Whisper (локально) | openai-whisper |
| Ollama + Mistral | latest |
| OpenAI (опционально) | gpt-4o + whisper-1 |
