import aiosqlite

async def init_db():
    async with aiosqlite.connect("users.db") as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                strt Boolean
            )
        """)
        await db.commit()

async def add_user(user_id: int, username: str) -> bool:
    async with aiosqlite.connect("users.db") as db:
        # Проверяем, существует ли пользователь
        async with db.execute("SELECT 1 FROM users WHERE user_id = ?", (user_id,)) as cursor:
            exists = await cursor.fetchone()
        if exists:
            # Пользователь уже существует – обновляем имя, если требуется
            await db.execute("UPDATE users SET username = ? WHERE user_id = ?", (username, user_id))
            await db.commit()
            return False
        else:
            # Пользователь новый – добавляем в базу
            await db.execute("INSERT INTO users (user_id, username, strt) VALUES (?, ?, ?)", (user_id, username, True))
            await db.commit()
            return True