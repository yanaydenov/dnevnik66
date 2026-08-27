import asyncio
import logging
from datetime import datetime, timezone
from config import REFRESH_INTERVAL_SEC, REFRESH_BEFORE_SEC
import database as db
from dnevnik_client import DnevnikClient, DnevnikUnauthorizedError

logger = logging.getLogger(__name__)


async def refresh_user_tokens(user_data: dict) -> bool:
    telegram_id = user_data["telegram_id"]
    access_token = user_data["access_token"]
    refresh_token = user_data["refresh_token"]

    client = DnevnikClient(access_token=access_token, refresh_token=refresh_token)
    try:
        new_tokens = await client.refresh_tokens()
        await db.save_tokens(
            telegram_id=telegram_id,
            access_token=new_tokens["accessToken"],
            refresh_token=new_tokens["refreshToken"],
        )
        logger.info(f"Successfully refreshed tokens for user {telegram_id}")
        return True
    except DnevnikUnauthorizedError as e:
        logger.warning(f"User {telegram_id} tokens invalid or expired: {e}. Clearing tokens.")
        await db.delete_tokens(telegram_id)
        return False
    except Exception as e:
        logger.error(f"Error refreshing tokens for user {telegram_id}: {e}")
        return False


async def run_tokens_refresher_loop(interval_sec: int = REFRESH_INTERVAL_SEC, threshold_sec: int = REFRESH_BEFORE_SEC):
    logger.info(f"Starting background tokens refresher loop (interval={interval_sec}s, threshold={threshold_sec}s)")
    while True:
        try:
            users_to_refresh = await db.get_users_for_refresh(threshold_seconds=threshold_sec)
            if users_to_refresh:
                logger.info(f"Found {len(users_to_refresh)} users requiring token refresh")
                for u in users_to_refresh:
                    await refresh_user_tokens(u)
                    await asyncio.sleep(0.5)  # slight delay between requests
        except Exception as e:
            logger.error(f"Unexpected error in token refresher loop: {e}", exc_info=True)

        await asyncio.sleep(interval_sec)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

    async def main():
        await db.init_db()
        await run_tokens_refresher_loop()

    asyncio.run(main())
