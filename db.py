import aiosqlite

async def init_db():
    async with aiosqlite.connect("users.db") as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT
            )
        """)
        await db.commit()

async def add_user(user_id: int, username: str):
    async with aiosqlite.connect("users.db") as db:
        await db.execute("""
            INSERT OR REPLACE INTO users (user_id, username)
            VALUES (?, ?)
        """, (user_id, username))
        await db.commit()
