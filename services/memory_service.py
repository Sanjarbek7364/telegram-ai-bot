"""
Xotira xizmati — SQLite database
Eslatmalar, suhbat tarixi, foydalanuvchi sozlamalari
"""
import aiosqlite
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "database", "bot.db")


async def init_db():
    """Ma'lumotlar bazasini yaratish"""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

    async with aiosqlite.connect(DB_PATH) as db:
        # Foydalanuvchilar jadvali
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                first_name TEXT,
                username TEXT,
                prayer_notify INTEGER DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Eslatmalar jadvali
        await db.execute("""
            CREATE TABLE IF NOT EXISTS memories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                content TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        """)

        # Suhbat tarixi (Gemini uchun qo'shimcha kontekst)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        """)

        await db.commit()


async def ensure_user(user_id: int, first_name: str = "", username: str = ""):
    """Foydalanuvchini bazaga qo'shish (agar yo'q bo'lsa)"""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR IGNORE INTO users (user_id, first_name, username) VALUES (?, ?, ?)",
            (user_id, first_name, username),
        )
        await db.commit()


# ============ ESLATMALAR ============

async def add_memory(user_id: int, content: str) -> int:
    """Eslatma qo'shish"""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "INSERT INTO memories (user_id, content) VALUES (?, ?)",
            (user_id, content),
        )
        await db.commit()
        return cursor.lastrowid


async def get_memories(user_id: int) -> list[dict]:
    """Barcha eslatmalarni olish"""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT id, content, created_at FROM memories WHERE user_id = ? ORDER BY created_at DESC",
            (user_id,),
        ) as cursor:
            rows = await cursor.fetchall()
            return [{"id": row["id"], "content": row["content"], "created_at": row["created_at"]} for row in rows]


async def delete_memory(user_id: int, memory_id: int) -> bool:
    """Eslatmani o'chirish"""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "DELETE FROM memories WHERE id = ? AND user_id = ?",
            (memory_id, user_id),
        )
        await db.commit()
        return cursor.rowcount > 0


async def get_all_memories_text(user_id: int) -> str:
    """Barcha eslatmalarni matn ko'rinishida olish (AI kontekst uchun)"""
    memories = await get_memories(user_id)
    if not memories:
        return ""
    lines = [f"- {m['content']}" for m in memories]
    return "Foydalanuvchi eslatmalari:\n" + "\n".join(lines)


# ============ NAMOZ SOZLAMALARI ============

async def set_prayer_notify(user_id: int, enabled: bool):
    """Namoz ogohlantirishni yoqish/o'chirish"""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET prayer_notify = ? WHERE user_id = ?",
            (1 if enabled else 0, user_id),
        )
        await db.commit()


async def get_prayer_notify(user_id: int) -> bool:
    """Namoz ogohlantirish holati"""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT prayer_notify FROM users WHERE user_id = ?",
            (user_id,),
        ) as cursor:
            row = await cursor.fetchone()
            return bool(row[0]) if row else False


async def get_prayer_subscribers() -> list[int]:
    """Namoz ogohlantirishga obuna bo'lgan foydalanuvchilar"""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT user_id FROM users WHERE prayer_notify = 1"
        ) as cursor:
            rows = await cursor.fetchall()
            return [row[0] for row in rows]


# ============ SUHBAT TARIXI ============

async def save_conversation(user_id: int, role: str, content: str):
    """Suhbat tarixiga qo'shish"""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO conversations (user_id, role, content) VALUES (?, ?, ?)",
            (user_id, role, content),
        )
        # Faqat oxirgi 50 ta xabarni saqlash
        await db.execute("""
            DELETE FROM conversations WHERE user_id = ? AND id NOT IN (
                SELECT id FROM conversations WHERE user_id = ?
                ORDER BY id DESC LIMIT 50
            )
        """, (user_id, user_id))
        await db.commit()
