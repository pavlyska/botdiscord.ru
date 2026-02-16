from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel
import aiosqlite
import os
from typing import List, Optional

app = FastAPI(title="Anti Raid Bot API")
DB_PATH = os.path.join(os.path.dirname(__file__), "../shared/database.db")

class SubscriptionUpdate(BaseModel):
    discord_id: int
    days: int
    source: str = "telegram"

class UserStatus(BaseModel):
    discord_id: int
    is_on_server: bool
    username: Optional[str] = None

async def get_db():
    db = await aiosqlite.connect(DB_PATH)
    try:
        yield db
    finally:
        await db.close()

@app.on_event("startup")
async def startup():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS subscriptions (
                discord_id INTEGER PRIMARY KEY,
                expiry_timestamp INTEGER,
                purchase_date INTEGER,
                source TEXT,
                role_id INTEGER
            )
        """)
        await db.commit()

@app.post("/add_subscription")
async def add_subscription(data: SubscriptionUpdate):
    # Этот эндпоинт будет вызываться ТГ ботом после оплаты
    # Реальная логика выдачи роли будет в ДС боте, 
    # API может просто записывать в БД или уведомлять ДС бота через очередь/webhook
    # Для простоты, ДС бот будет сам проверять БД
    import time
    expiry = int(time.time()) + (data.days * 86400)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO subscriptions (discord_id, expiry_timestamp, purchase_date, source)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(discord_id) DO UPDATE SET
            expiry_timestamp = expiry_timestamp + ?,
            source = ?
        """, (data.discord_id, expiry, int(time.time()), data.source, data.days * 86400, data.source))
        await db.commit()
    return {"status": "success", "discord_id": data.discord_id, "new_expiry": expiry}

@app.get("/check_user/{discord_id}")
async def check_user(discord_id: int):
    # Этот эндпоинт будет запрашивать у ДС бота, есть ли юзер на сервере
    # В данной архитектуре API и ДС бот могут делить одну БД или ДС бот может иметь свой внутренний API
    # Для простоты ТГ бот будет слать запрос сюда, а API проверит статус в БД или через IPC
    return {"discord_id": discord_id, "status": "pending_implementation"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
