import asyncio
import logging
from datetime import datetime
from typing import Dict, Any, List
from aiogram import Bot

from config import NOTIFY_INTERVAL_SEC, NOTIFY_ENABLED, SCHOOL_YEAR
import database as db
from dnevnik_client import DnevnikClient, DnevnikUnauthorizedError
import rich_formatters as rf

logger = logging.getLogger("dnevnik_notifier")


def _extract_grades_snapshot(period_data: Dict[str, Any]) -> Dict[str, List[Any]]:
    """Extracts a simple dict of subject -> list of grades for snapshot comparison"""
    disciplines = period_data.get("disciplines") or []
    snapshot: Dict[str, List[Any]] = {}
    for d in disciplines:
        name = d.get("name") or ""
        grades = d.get("grades") or []
        flat_grades = []
        for g in grades:
            if isinstance(g, list):
                flat_grades.append("/".join(str(x) for x in g))
            else:
                flat_grades.append(str(g))
        snapshot[name] = flat_grades
    return snapshot


def _find_new_grades(old_snap: Dict[str, List[Any]], new_snap: Dict[str, List[Any]], period_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Finds newly added grades by comparing previous and current snapshots"""
    new_items: List[Dict[str, Any]] = []
    disciplines = {d.get("name", ""): d for d in (period_data.get("disciplines") or [])}

    for subj, new_grades in new_snap.items():
        old_grades = old_snap.get(subj, [])
        if len(new_grades) > len(old_grades):
            # Newly added grades are the tail
            added = new_grades[len(old_grades):]
            d_info = disciplines.get(subj, {})
            avg = d_info.get("average", 0.0)
            for g in added:
                new_items.append({
                    "subject": subj,
                    "grade": g,
                    "average": avg,
                })
    return new_items


async def check_user_grades(bot: Bot, user_id: int) -> None:
    user = await db.get_user(user_id)
    if not user or not user.get("access_token") or not user.get("refresh_token"):
        return

    meta = user.get("meta", {})
    if meta.get("notify_enabled", True) is False:
        return

    school_year = meta.get("school_year") or SCHOOL_YEAR or None

    async def on_refreshed(new_access: str, new_refresh: str):
        current_meta = user.get("meta", {})
        await db.save_tokens(user_id, new_access, new_refresh, meta=current_meta)

    client = DnevnikClient(
        access_token=user["access_token"],
        refresh_token=user["refresh_token"],
        school_year=school_year,
        on_token_refreshed=on_refreshed,
    )

    try:
        await client.init_ids()
        period_data = await client.grades_period(0)
        current_snapshot = _extract_grades_snapshot(period_data)

        old_snapshot = meta.get("grades_snapshot")
        if old_snapshot is not None and isinstance(old_snapshot, dict):
            new_grades = _find_new_grades(old_snapshot, current_snapshot, period_data)
            if new_grades:
                logger.info(f"Detected {len(new_grades)} new grades for user {user_id}")
                blocks = rf.rich_new_grades_notification(new_grades)
                fallback = "⚡️ В электронном дневнике появились новые оценки!"
                from bot import send_rich_msg
                await send_rich_msg(bot, user_id, blocks, fallback)

        # Update snapshot in user's meta
        meta["grades_snapshot"] = current_snapshot
        await db.save_tokens(user_id, user["access_token"], user["refresh_token"], meta=meta)

    except DnevnikUnauthorizedError:
        logger.warning(f"User {user_id} unauthorized during grade polling. Removing tokens and alerting user.")
        from bot import handle_unauthorized_user
        await handle_unauthorized_user(bot, user_id, user_id)
    except Exception as e:
        logger.debug(f"Grade check skipped for user {user_id}: {e}")


async def run_grade_notifier_loop(bot: Bot, interval_sec: int = NOTIFY_INTERVAL_SEC):
    """Background task polling for new grades every interval_sec (default: 40 min) during daytime"""
    if not NOTIFY_ENABLED:
        logger.info("Grade notifications background loop is disabled in configuration.")
        return

    logger.info(f"Starting grade notifier background loop (interval={interval_sec}s / {interval_sec // 60} min)")
    # Initial sleep to let bot start completely
    await asyncio.sleep(10)

    while True:
        try:
            now = datetime.now()
            # Only poll during daytime (08:00 - 20:00) and skip Sundays (weekday 6)
            if 8 <= now.hour < 20 and now.weekday() != 6:
                user_ids = await db.get_all_user_ids()
                if user_ids:
                    logger.debug(f"Checking new grades for {len(user_ids)} users...")
                    for uid in user_ids:
                        await check_user_grades(bot, uid)
                        await asyncio.sleep(1.5)  # Jitter delay to avoid burst requests
            else:
                logger.debug("Night or Sunday: grade polling sleeping...")
        except Exception as e:
            logger.error(f"Unexpected error in grade notifier loop: {e}", exc_info=True)

        await asyncio.sleep(interval_sec)
