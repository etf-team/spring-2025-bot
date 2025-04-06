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

        async with db.execute("SELECT 1 FROM users WHERE user_id = ?", (user_id,)) as cursor:
            exists = await cursor.fetchone()
        if exists:
            await db.execute("UPDATE users SET username = ? WHERE user_id = ?", (username, user_id))
            await db.commit()
            return False
        else:
            await db.execute("INSERT INTO users (user_id, username, strt) VALUES (?, ?, ?)", (user_id, username, True))
            await db.commit()
            return True

async def get_all_users():
    async with aiosqlite.connect("users.db") as db:
        async with db.execute("SELECT user_id FROM users") as cursor:
            rows = await cursor.fetchall()
            return [row[0] for row in rows]