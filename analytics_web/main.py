from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import create_engine, text
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv

load_dotenv()

app = FastAPI()
templates = Jinja2Templates(directory="analytics_web/templates")

engine = create_engine(os.getenv("DATABASE_URL"))
ANALYTICS_PASSWORD = os.getenv("ANALYTICS_PASSWORD", "admin123")


def check_password(password: str = ""):
    if password != ANALYTICS_PASSWORD:
        raise HTTPException(status_code=403, detail="Неверный пароль")
    return True


def get_metrics():
    with engine.connect() as conn:
        # Всего пользователей
        total_users = conn.execute(text(
            "SELECT COUNT(*) FROM users WHERE is_onboarded = true AND role = 'owner'"
        )).scalar()

        # Платящих пользователей
        paying_users = conn.execute(text(
            "SELECT COUNT(*) FROM users WHERE is_subscribed = true"
        )).scalar()

        # Конверсия триал → платный
        conversion = round((paying_users / total_users * 100) if total_users > 0 else 0, 1)

        # Всего записей
        total_entries = conn.execute(text(
            "SELECT COUNT(*) FROM entries WHERE source = 'owner'"
        )).scalar()

        # Выполненных задач
        done_tasks = conn.execute(text(
            "SELECT COUNT(*) FROM entries WHERE category = 'task' AND is_done = true"
        )).scalar()

        # Незакрытых задач
        open_tasks = conn.execute(text(
            "SELECT COUNT(*) FROM entries WHERE category = 'task' AND is_done = false AND archived_at IS NULL"
        )).scalar()

        # % выполненных задач
        total_tasks = conn.execute(text(
            "SELECT COUNT(*) FROM entries WHERE category = 'task'"
        )).scalar()
        done_pct = round((done_tasks / total_tasks * 100) if total_tasks > 0 else 0, 1)

        # Гостевые записи
        guest_entries = conn.execute(text(
            "SELECT COUNT(*) FROM entries WHERE source = 'guest'"
        )).scalar()

        # Зомби-задачи (remind_count >= 3, не выполнены)
        zombie_tasks = conn.execute(text(
            "SELECT COUNT(*) FROM entries WHERE category = 'task' AND is_done = false AND remind_count >= 3"
        )).scalar()

        # Активные за последние 7 дней
        week_ago = (datetime.utcnow() - timedelta(days=7)).strftime("%Y-%m-%d")
        active_7d = conn.execute(text(
            f"SELECT COUNT(DISTINCT user_id) FROM entries WHERE created_at >= '{week_ago}'"
        )).scalar()

        # Записи по категориям
        cat_rows = conn.execute(text(
            "SELECT category, COUNT(*) as cnt FROM entries WHERE source='owner' GROUP BY category ORDER BY cnt DESC"
        )).fetchall()
        categories = [{"name": r[0] or "chaos", "count": r[1]} for r in cat_rows]

        # Новые пользователи по дням (последние 14 дней)
        new_users_rows = conn.execute(text(
            "SELECT DATE(created_at) as day, COUNT(*) as cnt FROM users "
            "WHERE created_at >= NOW() - INTERVAL '14 days' "
            "GROUP BY day ORDER BY day"
        )).fetchall()
        new_users = [{"day": str(r[0]), "count": r[1]} for r in new_users_rows]

        # Записи по дням (последние 14 дней)
        entries_rows = conn.execute(text(
            "SELECT DATE(created_at) as day, COUNT(*) as cnt FROM entries "
            "WHERE created_at >= NOW() - INTERVAL '14 days' "
            "GROUP BY day ORDER BY day"
        )).fetchall()
        entries_by_day = [{"day": str(r[0]), "count": r[1]} for r in entries_rows]

        # Список пользователей
        users_rows = conn.execute(text(
            "SELECT user_id, username, first_name, is_subscribed, trial_start, created_at, "
            "(SELECT COUNT(*) FROM entries e WHERE e.user_id = users.user_id) as entries_count "
            "FROM users WHERE role = 'owner' ORDER BY created_at DESC LIMIT 50"
        )).fetchall()
        users = [{
            "user_id": r[0],
            "username": r[1] or "—",
            "first_name": r[2] or "—",
            "is_subscribed": r[3],
            "trial_start": r[4].strftime("%d.%m.%Y") if r[4] else "—",
            "created_at": r[5].strftime("%d.%m.%Y") if r[5] else "—",
            "entries_count": r[6]
        } for r in users_rows]

        return {
            "total_users": total_users,
            "paying_users": paying_users,
            "conversion": conversion,
            "total_entries": total_entries,
            "done_tasks": done_tasks,
            "open_tasks": open_tasks,
            "done_pct": done_pct,
            "guest_entries": guest_entries,
            "zombie_tasks": zombie_tasks,
            "active_7d": active_7d,
            "categories": categories,
            "new_users": new_users,
            "entries_by_day": entries_by_day,
            "users": users,
            "generated_at": datetime.now().strftime("%d.%m.%Y %H:%M")
        }


@app.get("/", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})


@app.get("/analytics", response_class=HTMLResponse)
async def analytics(request: Request, password: str = ""):
    check_password(password)
    metrics = get_metrics()
    return templates.TemplateResponse("dashboard.html", {"request": request, "m": metrics, "password": password})


# ── Вебхук оплаты ────────────────────────────────────────────────────────
@app.post("/payment-webhook")
async def payment_webhook(request: Request):
    import httpx
    data = await request.json()

    user_id = data.get("user_id")
    amount = data.get("amount", "299")
    username = data.get("username", "—")

    if user_id:
        bot_token = os.getenv("BOT_TOKEN")
        text_msg = f"💰 Оплата получена!\n\nПодписка оформлена на 30 дней. Спасибо! 🧠"
        async with httpx.AsyncClient() as client:
            await client.post(
                f"https://api.telegram.org/bot{bot_token}/sendMessage",
                json={"chat_id": user_id, "text": text_msg}
            )

    return {"ok": True}
