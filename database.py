import json
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List
import aiosqlite
from cryptography.fernet import Fernet
import jwt
from config import DATABASE_PATH, SECRET_KEY

logger = logging.getLogger(__name__)

# Initialize cipher
fernet = Fernet(SECRET_KEY.encode() if isinstance(SECRET_KEY, str) else SECRET_KEY)


def encrypt(text: Optional[str]) -> Optional[str]:
    if not text:
        return None
    return fernet.encrypt(text.encode()).decode()


def decrypt(cipher_text: Optional[str]) -> Optional[str]:
    if not cipher_text:
        return None
    try:
        return fernet.decrypt(cipher_text.encode()).decode()
    except Exception as e:
        logger.error(f"Failed to decrypt token: {e}")
        return None


def get_jwt_exp(token: str) -> Optional[datetime]:
    try:
        payload = jwt.decode(token, options={"verify_signature": False})
        exp = payload.get("exp")
        if exp:
            return datetime.fromtimestamp(exp, tz=timezone.utc)
    except Exception as e:
        logger.debug(f"Failed to parse JWT exp: {e}")
    return None


async def init_db():
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                telegram_id INTEGER PRIMARY KEY,
                access_token TEXT,
                refresh_token TEXT,
                token_expires_at TIMESTAMP,
                selected_student_id TEXT,
                meta TEXT,
                tokens_updated_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.execute("CREATE INDEX IF NOT EXISTS idx_token_exp ON users(token_expires_at)")
        await db.commit()
    logger.info("Database initialized")


async def get_user(telegram_id: int) -> Optional[Dict[str, Any]]:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM users WHERE telegram_id = ?", (telegram_id,))
        row = await cursor.fetchone()
        if not row:
            return None

        access_token = decrypt(row["access_token"])
        refresh_token = decrypt(row["refresh_token"])

        meta_dict = {}
        if row["meta"]:
            try:
                meta_dict = json.loads(row["meta"])
            except Exception:
                pass

        return {
            "telegram_id": row["telegram_id"],
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_expires_at": row["token_expires_at"],
            "selected_student_id": row["selected_student_id"],
            "tokens_updated_at": row["tokens_updated_at"],
            "meta": meta_dict,
        }


async def save_tokens(
    telegram_id: int,
    access_token: str,
    refresh_token: str,
    meta: Optional[Dict[str, Any]] = None,
    selected_student_id: Optional[str] = None
):
    enc_access = encrypt(access_token)
    enc_refresh = encrypt(refresh_token)
    exp_date = get_jwt_exp(access_token)
    exp_iso = exp_date.isoformat() if exp_date else None
    now_iso = datetime.now(timezone.utc).isoformat()
    meta_json = json.dumps(meta or {}, ensure_ascii=False)

    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("""
            INSERT INTO users (telegram_id, access_token, refresh_token, token_expires_at, meta, tokens_updated_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(telegram_id) DO UPDATE SET
                access_token = excluded.access_token,
                refresh_token = excluded.refresh_token,
                token_expires_at = excluded.token_expires_at,
                meta = CASE WHEN excluded.meta != '{}' THEN excluded.meta ELSE users.meta END,
                tokens_updated_at = excluded.tokens_updated_at,
                updated_at = excluded.updated_at
        """, (telegram_id, enc_access, enc_refresh, exp_iso, meta_json, now_iso, now_iso))

        if selected_student_id:
            await db.execute("UPDATE users SET selected_student_id = ? WHERE telegram_id = ?", (selected_student_id, telegram_id))

        await db.commit()


async def set_selected_student(telegram_id: int, student_id: str):
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("UPDATE users SET selected_student_id = ?, updated_at = ? WHERE telegram_id = ?", (student_id, datetime.now(timezone.utc).isoformat(), telegram_id))
        await db.commit()


async def delete_tokens(telegram_id: int):
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("""
            UPDATE users SET
                access_token = NULL,
                refresh_token = NULL,
                token_expires_at = NULL,
                tokens_updated_at = NULL,
                updated_at = ?
            WHERE telegram_id = ?
        """, (datetime.now(timezone.utc).isoformat(), telegram_id))
        await db.commit()


async def get_users_for_refresh(threshold_seconds: int = 600) -> List[Dict[str, Any]]:
    """Returns users whose token expires in less than threshold_seconds or has already expired"""
    now = datetime.now(timezone.utc)
    threshold_time = (now + timedelta(seconds=threshold_seconds)).isoformat()

    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("""
            SELECT telegram_id, access_token, refresh_token, token_expires_at
            FROM users
            WHERE access_token IS NOT NULL
              AND refresh_token IS NOT NULL
              AND (token_expires_at IS NULL OR token_expires_at <= ?)
        """, (threshold_time,))
        rows = await cursor.fetchall()

        result = []
        for row in rows:
            acc = decrypt(row["access_token"])
            ref = decrypt(row["refresh_token"])
            if acc and ref:
                result.append({
                    "telegram_id": row["telegram_id"],
                    "access_token": acc,
                    "refresh_token": ref,
                    "token_expires_at": row["token_expires_at"],
                })
        return result


async def get_all_user_ids() -> List[int]:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cursor = await db.execute("SELECT telegram_id FROM users WHERE access_token IS NOT NULL")
        rows = await cursor.fetchall()
        return [row[0] for row in rows]
