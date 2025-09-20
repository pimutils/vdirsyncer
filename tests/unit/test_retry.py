from __future__ import annotations

import json
from unittest.mock import AsyncMock, Mock

import aiohttp
import pytest
from aioresponses import aioresponses

from vdirsyncer.exceptions import Error as VdirsyncerError
from vdirsyncer.http import UsageLimitReached, request


async def _create_mock_response(status: int, body: str | dict):
    raw_body = body
    text_body = json.dumps(body) if isinstance(body, dict) else body

    mock_response = AsyncMock()
    mock_response.status = status
    mock_response.ok = 200 <= status < 300
    mock_response.reason = "OK" if mock_response.ok else "Forbidden"
    mock_response.headers = (
        {"Content-Type": "application/json"}
        if isinstance(raw_body, dict)
        else {"Content-Type": "text/plain"}
    )
    mock_response.text.return_value = text_body
    if isinstance(raw_body, dict):
        mock_response.json.return_value = raw_body
    else:
        mock_response.json.side_effect = ValueError("Not JSON")
    mock_response.raise_for_status = Mock(
        side_effect=(
            aiohttp.ClientResponseError(
                request_info=AsyncMock(),
                history=(),
                status=status,
                message=mock_response.reason,
                headers=mock_response.headers,
            )
            if not mock_response.ok
            else None
        )
    )

    return mock_response


@pytest.mark.asyncio
async def test_request_retry_on_usage_limit():
    url = "http://example.com/api"
    max_retries = 5  # As configured in the @retry decorator

    mock_session = AsyncMock()

    # Simulate (max_retries - 1) 403 errors and then a 200 OK
    mock_session.request.side_effect = [
        await _create_mock_response(
            403,
            {
                "error": {
                    "errors": [{"domain": "usageLimits", "reason": "quotaExceeded"}]
                }
            },
        )
        for _ in range(max_retries - 1)
    ] + [await _create_mock_response(200, "OK")]

    async with (
        aiohttp.ClientSession()
    ):  # Dummy session. Will be replaced by mock_session at call
        response = await request("GET", url, mock_session)

        assert response.status == 200
        assert mock_session.request.call_count == max_retries


@pytest.mark.asyncio
async def test_request_retry_exceeds_max_attempts():
    url = "http://example.com/api"
    max_retries = 5  # As configured in the @retry decorator

    mock_session = AsyncMock()
    # Simulate max_retries 403 errors and then a 200 OK
    mock_session.request.side_effect = [
        await _create_mock_response(
            403,
            {
                "error": {
                    "errors": [{"domain": "usageLimits", "reason": "quotaExceeded"}]
                }
            },
        )
        for _ in range(max_retries)
    ]

    async with (
        aiohttp.ClientSession()
    ):  # Dummy session. Will be replaced by mock_session at call
        with pytest.raises(UsageLimitReached):
            await request("GET", url, mock_session)
        assert mock_session.request.call_count == max_retries


@pytest.mark.asyncio
async def test_request_no_retry_on_generic_403_json():
    url = "http://example.com/api"

    mock_session = AsyncMock()
    # Generic non-Google 403 error payload (e.g., GitHub-style)
    mock_session.request.side_effect = [
        await _create_mock_response(403, {"message": "API rate limit exceeded"})
    ]

    async with aiohttp.ClientSession():
        with pytest.raises(aiohttp.ClientResponseError):
            await request("GET", url, mock_session)
        # Should not retry because it's not the Google quotaExceeded shape
        assert mock_session.request.call_count == 1


@pytest.mark.asyncio
async def test_request_no_retry_on_generic_403_text():
    url = "http://example.com/api"

    mock_session = AsyncMock()
    # Plain-text 403 body mentioning rate limits, but not structured as Google error
    mock_session.request.side_effect = [
        await _create_mock_response(403, "Rate limit exceeded")
    ]

    async with aiohttp.ClientSession():
        with pytest.raises(aiohttp.ClientResponseError):
            await request("GET", url, mock_session)
        # Should not retry because the JSON shape is not Google quotaExceeded
        assert mock_session.request.call_count == 1
