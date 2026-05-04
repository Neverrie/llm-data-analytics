from __future__ import annotations

import pytest

from app.services.openrouter_client import OpenRouterClient, OpenRouterClientError


@pytest.mark.asyncio
async def test_openrouter_client_missing_key() -> None:
    client = OpenRouterClient(api_key=None)
    with pytest.raises(OpenRouterClientError) as exc:
        await client.chat(messages=[{"role": "user", "content": "hello"}])
    assert "OPENROUTER_API_KEY is not configured" in str(exc.value)
