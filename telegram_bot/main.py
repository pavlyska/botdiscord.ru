import asyncio
import logging
import os
import aiosqlite
import aiohttp
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import LabeledPrice, PreCheckoutQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

API_TOKEN = 'YOUR_TELEGRAM_BOT_TOKEN'
API_SERVER_URL = "http://localhost:8000"
DB_PATH = os.path.join(os.path.dirname(__file__), "../shared/database.db")

# Цены в звездах (примерные, 1 звезда ~ 2 рубля, но вы можете настроить)
# 1 месяц - 50р -> 25 звезд
# 2 месяца - 100р -> 50 звезд
# 3 месяца - 150р -> 75 звезд
# 6 месяцев - 290р -> 145 звезд
# 12 месяцев - 549р -> 275 звезд

PRICES = {
    "1_month": {"days": 30, "price": 25, "label": "1 месяц - 50р (25 звезд)"},
    "2_months": {"days": 60, "price": 50, "label": "2 месяца - 100р (50 звезд)"},
    "3_months": {"days": 90, "price": 75, "label": "3 месяца - 150р (75 звезд)"},
    "6_months": {"days": 180, "price": 145, "label": "6 месяцев - 290р (145 звезд)"},
    "12_months": {"days": 365, "price": 275, "label": "12 месяцев - 549р (275 звезд)"},
}

bot = Bot(token=API_TOKEN)
dp = Dispatcher()

async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS tg_users (
                tg_id INTEGER PRIMARY KEY,
                discord_id INTEGER
            )
        """)
        await db.commit()

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="Купить подписку", callback_data="buy_menu"))
    builder.row(InlineKeyboardButton(text="Другие способы оплаты", url="https://antiraidbot.ru/premium/"))
    
    await message.answer(
        "👋 Привет! Здесь вы можете купить премиум подписку за **Звезды Telegram**.\n\n"
        "Для начала покупки нажмите кнопку ниже.",
        reply_markup=builder.as_markup()
    )

@dp.callback_query(F.data == "buy_menu")
async def buy_menu(callback: types.CallbackQuery):
    await callback.message.answer("Введите ваш Discord ID или Username:")
    # В реальном боте здесь нужно использовать FSM для ожидания ввода
    # Для примера обработаем следующее сообщение

@dp.message(F.text)
async def handle_discord_id(message: types.Message):
    # Простая имитация проверки
    discord_id = message.text # Здесь должна быть логика извлечения ID
    
    # Запрос к API для проверки юзера на сервере
    async with aiohttp.ClientSession() as session:
        async with session.get(f"{API_SERVER_URL}/check_user/{discord_id}") as resp:
            # data = await resp.json()
            # if not data['is_on_server']:
            #     return await message.answer("Вас нет на сервере! Зайдите: [ссылка]")
            pass

    # Сохраняем связь (в реальном коде через FSM)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT OR REPLACE INTO tg_users (tg_id, discord_id) VALUES (?, ?)", (message.from_user.id, discord_id))
        await db.commit()

    builder = InlineKeyboardBuilder()
    for key, val in PRICES.items():
        builder.row(InlineKeyboardButton(text=val['label'], callback_data=f"pay_{key}"))
    
    await message.answer("Выберите период подписки:", reply_markup=builder.as_markup())

@dp.callback_query(F.data.startswith("pay_"))
async def process_payment(callback: types.CallbackQuery):
    plan_key = callback.data.split("_", 1)[1]
    if plan_key not in PRICES: return
    
    plan = PRICES[plan_key]
    
    await bot.send_invoice(
        chat_id=callback.message.chat.id,
        title=f"Премиум подписка: {plan['label']}",
        description=f"Активация премиум функций на {plan['days']} дней",
        payload=f"sub_{plan_key}",
        provider_token="", # Пусто для звезд
        currency="XTR", # Код для звезд
        prices=[LabeledPrice(label="Звезды", amount=plan['price'])]
    )

@dp.pre_checkout_query()
async def process_pre_checkout(pre_checkout_query: PreCheckoutQuery):
    await bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)

@dp.message(F.successful_payment)
async def success_payment(message: types.Message):
    payload = message.successful_payment.invoice_payload
    plan_key = payload.split("_", 1)[1]
    days = PRICES[plan_key]['days']
    
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT discord_id FROM tg_users WHERE tg_id = ?", (message.from_user.id,)) as cursor:
            row = await cursor.fetchone()
            if row:
                discord_id = row[0]
                # Отправляем запрос к API для начисления
                async with aiohttp.ClientSession() as session:
                    payload = {"discord_id": int(discord_id), "days": days, "source": "telegram_stars"}
                    async with session.post(f"{API_SERVER_URL}/add_subscription", json=payload) as resp:
                        if resp.status == 200:
                            await message.answer("✅ Оплата прошла успешно! Подписка активирована в Discord.")
                        else:
                            await message.answer("❌ Ошибка при активации. Обратитесь в поддержку.")

async def main():
    await init_db()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
