import discord
from discord.ext import commands, tasks
import aiosqlite
import datetime
import time
import os
import asyncio

TOKEN = "YOUR_DISCORD_BOT_TOKEN"
GUILD_ID = 1234567890  # ID вашего сервера
PREMIUM_ROLE_ID = 1234567890  # ID премиум роли
BOOSTY_APP_ID = 669952145352556561
ADMIN_IDS = [677883972344217616]

DB_PATH = os.path.join(os.path.dirname(__file__), "../shared/database.db")

intents = discord.Intents.default()
intents.members = True
intents.message_content = True

bot = commands.Bot(command_prefix="/", intents=intents)

async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS subscriptions (
                discord_id INTEGER PRIMARY KEY,
                expiry_timestamp INTEGER,
                purchase_date INTEGER,
                source TEXT
            )
        """)
        await db.commit()

@bot.event
async def on_ready():
    await init_db()
    check_subscriptions.start()
    print(f"Logged in as {bot.user}")

@tasks.loop(minutes=1)
async def check_subscriptions():
    now = int(time.time())
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT discord_id FROM subscriptions WHERE expiry_timestamp <= ?", (now,)) as cursor:
            expired_users = await cursor.fetchall()
            
        for (user_id,) in expired_users:
            guild = bot.get_guild(GUILD_ID)
            if guild:
                member = guild.get_member(user_id)
                if member:
                    role = guild.get_role(PREMIUM_ROLE_ID)
                    if role in member.roles:
                        try:
                            await member.remove_roles(role, reason="Subscription expired")
                        except:
                            pass
            await db.execute("DELETE FROM subscriptions WHERE discord_id = ?", (user_id,))
        await db.commit()

@bot.event
async def on_member_update(before, after):
    # Контроль снятия роли
    role = after.guild.get_role(PREMIUM_ROLE_ID)
    if role in before.roles and role not in after.roles:
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT expiry_timestamp FROM subscriptions WHERE discord_id = ?", (after.id,)) as cursor:
                row = await cursor.fetchone()
                if row and row[0] > int(time.time()):
                    # Подписка еще активна, возвращаем роль
                    try:
                        await after.add_roles(role, reason="Subscription still active")
                    except:
                        pass

@bot.event
async def on_member_join(member):
    # Возврат роли при входе
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT expiry_timestamp FROM subscriptions WHERE discord_id = ?", (member.id,)) as cursor:
            row = await cursor.fetchone()
            if row and row[0] > int(time.time()):
                role = member.guild.get_role(PREMIUM_ROLE_ID)
                if role:
                    try:
                        await member.add_roles(role, reason="Returning subscriber")
                    except:
                        pass

@bot.command(name="give")
async def give(ctx, user: discord.User, days: int):
    if ctx.author.id not in ADMIN_IDS:
        return await ctx.send("У вас нет прав.")
    
    expiry = int(time.time()) + (days * 86400)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO subscriptions (discord_id, expiry_timestamp, purchase_date, source)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(discord_id) DO UPDATE SET
            expiry_timestamp = expiry_timestamp + ?,
            source = 'manual'
        """, (user.id, expiry, int(time.time()), 'manual', days * 86400))
        await db.commit()
    
    guild = bot.get_guild(GUILD_ID)
    member = guild.get_member(user.id)
    if member:
        role = guild.get_role(PREMIUM_ROLE_ID)
        await member.add_roles(role)
    
    await ctx.send(f"Премиум выдан пользователю {user.mention} на {days} дней.")

@bot.command(name="take")
async def take(ctx, user: discord.User):
    if ctx.author.id not in ADMIN_IDS:
        return await ctx.send("У вас нет прав.")
    
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM subscriptions WHERE discord_id = ?", (user.id,))
        await db.commit()
    
    guild = bot.get_guild(GUILD_ID)
    member = guild.get_member(user.id)
    if member:
        role = guild.get_role(PREMIUM_ROLE_ID)
        if role in member.roles:
            await member.remove_roles(role)
            
    await ctx.send(f"Премиум снят у пользователя {user.mention}.")

@bot.command(name="status")
async def status(ctx, user: discord.User = None):
    user = user or ctx.author
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT expiry_timestamp, purchase_date, source FROM subscriptions WHERE discord_id = ?", (user.id,)) as cursor:
            row = await cursor.fetchone()
            
    if not row:
        return await ctx.send(f"У пользователя {user.mention} нет активной подписки.")
    
    expiry, purchase, source = row
    remaining = expiry - int(time.time())
    days = remaining // 86400
    hours = (remaining % 86400) // 3600
    
    purchase_dt = datetime.datetime.fromtimestamp(purchase).strftime('%Y-%m-%d %H:%M:%S')
    
    msg = f"**Информация о подписке {user.mention}:**\n"
    msg += f"Когда была куплена: {purchase_dt}\n"
    msg += f"Сколько осталось: {max(0, days)} дн. {max(0, hours)} час.\n"
    
    if source == str(BOOSTY_APP_ID) or source == 'boosty':
        msg += "\nПодписка была куплена через Boosty, данные о подписке доступны на сайте."
        
    await ctx.send(msg)

bot.run(TOKEN)
