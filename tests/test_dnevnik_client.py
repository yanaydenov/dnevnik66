import pytest
from dnevnik_client import DnevnikClient, DnevnikUnauthorizedError, DnevnikExternalServerError


def test_dnevnik_client_headers():
    client = DnevnikClient(access_token="test_token_123", refresh_token="test_refresh_456")
    headers = client._headers()
    assert headers["authorization"] == "Bearer test_token_123"
    assert headers["accept"] == "application/json"


@pytest.mark.asyncio
async def test_dnevnik_client_no_refresh_token():
    client = DnevnikClient(access_token="test", refresh_token="")
    with pytest.raises(DnevnikUnauthorizedError):
        await client.refresh_tokens()
