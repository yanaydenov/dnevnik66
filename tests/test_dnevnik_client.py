import pytest
from unittest.mock import AsyncMock, patch
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


@pytest.mark.asyncio
async def test_init_ids_passes_class_id():
    client = DnevnikClient(access_token="test", refresh_token="refresh")

    client.get_students = AsyncMock(return_value={
        "students": [{"id": "student-1", "firstName": "Иван"}]
    })

    async def mock_request(method, path, **kwargs):
        params = kwargs.get("params", {})
        if path == "/estimate/years":
            return {"currentYear": {"id": 2025}, "years": [{"id": 2025}, {"id": 2024}]}
        elif path == "/classes":
            return {"currentClass": {"value": "class-abc-123"}}
        elif path == "/estimate/periods":
            assert params.get("classId") == "class-abc-123"
            assert params.get("schoolYear") == "2025"
            return {"periods": [{"id": "p1"}, {"id": "p2"}, {"id": "p3"}, {"id": "p4"}, {"id": "p5"}, {"id": "p6"}]}
        return {}

    client._request = AsyncMock(side_effect=mock_request)

    await client.init_ids()

    assert client.student_id == "student-1"
    assert client.class_id == "class-abc-123"
    assert client.school_year == "2025"
    assert len(client.periods_ids) == 6
