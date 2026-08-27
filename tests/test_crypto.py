import pytest
import os
from database import encrypt, decrypt, init_db, save_tokens, get_user, delete_tokens, get_jwt_exp
import jwt
from datetime import datetime, timezone, timedelta


def test_encrypt_decrypt():
    original = "my-secret-access-token-12345"
    encrypted = encrypt(original)
    assert encrypted != original
    decrypted = decrypt(encrypted)
    assert decrypted == original


def test_encrypt_decrypt_none():
    assert encrypt(None) is None
    assert decrypt(None) is None


def test_jwt_exp_parser():
    future_exp = int((datetime.now(timezone.utc) + timedelta(hours=1)).timestamp())
    token = jwt.encode({"sub": "user1", "exp": future_exp}, "secret_key_at_least_32_bytes_long_123456", algorithm="HS256")
    parsed_exp = get_jwt_exp(token)
    assert parsed_exp is not None
    assert abs(parsed_exp.timestamp() - future_exp) < 2


@pytest.mark.asyncio
async def test_db_token_storage(tmp_path, monkeypatch):
    test_db = str(tmp_path / "test.db")
    monkeypatch.setattr("config.DATABASE_PATH", test_db)
    monkeypatch.setattr("database.DATABASE_PATH", test_db)

    await init_db()

    user_id = 999888
    access = "access_token_secret_value"
    refresh = "refresh_token_secret_value"

    await save_tokens(telegram_id=user_id, access_token=access, refresh_token=refresh, meta={"name": "Ivan"})

    loaded = await get_user(user_id)
    assert loaded is not None
    assert loaded["access_token"] == access
    assert loaded["refresh_token"] == refresh
    assert loaded["meta"]["name"] == "Ivan"

    await delete_tokens(user_id)
    cleared = await get_user(user_id)
    assert cleared["access_token"] is None
    assert cleared["refresh_token"] is None
