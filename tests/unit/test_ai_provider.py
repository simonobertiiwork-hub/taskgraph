import json

import httpx
import pytest

from app.ai.errors import LLMInvalidResponseError, LLMUnavailableError
from app.ai.provider import OpenAICompatibleLLMProvider


def provider_response(*, message, model="qwen2.5:1.5b"):
    return {
        "id": "chatcmpl-local-1",
        "model": model,
        "choices": [{"message": message}],
        "usage": {
            "prompt_tokens": 120,
            "completion_tokens": 40,
            "total_tokens": 160,
        },
    }


def make_provider(http_client, **overrides):
    options = {
        "http_client": http_client,
        "base_url": "http://ollama:11434/v1",
        "api_key": "ollama",
        "model": "qwen2.5:1.5b",
        "provider": "ollama",
        "max_retries": 2,
        "backoff_seconds": 0,
    }
    options.update(overrides)
    return OpenAICompatibleLLMProvider(**options)


@pytest.mark.asyncio
async def test_provider_sends_real_tools_and_normalizes_calls():
    async def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        assert request.url.path == "/v1/chat/completions"
        assert payload["tool_choice"] == "required"
        assert payload["tools"][0]["function"]["name"] == "get_run_summary"
        return httpx.Response(
            200,
            json=provider_response(
                message={
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [
                        {
                            "id": "call-1",
                            "type": "function",
                            "function": {
                                "name": "get_run_summary",
                                "arguments": '{"run_id":"00000000-0000-0000-0000-000000000001"}',
                            },
                        }
                    ],
                }
            ),
            headers={"x-request-id": "provider-request-1"},
        )

    tools = [
        {
            "type": "function",
            "function": {"name": "get_run_summary", "parameters": {}},
        }
    ]
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        completion = await make_provider(http).choose_tools(
            messages=[{"role": "user", "content": "data"}],
            tools=tools,
        )

    assert completion.tool_calls[0].tool_name == "get_run_summary"
    assert completion.tool_calls[0].arguments["run_id"].endswith("1")
    assert completion.provider_request_id == "provider-request-1"
    assert completion.usage is not None
    assert completion.usage.total_tokens == 160


@pytest.mark.asyncio
async def test_provider_requests_strict_json_schema():
    async def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        assert payload["response_format"]["type"] == "json_schema"
        assert payload["response_format"]["json_schema"]["strict"] is True
        return httpx.Response(
            200,
            json=provider_response(
                message={"role": "assistant", "content": '{"ok":true}'}
            ),
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        completion = await make_provider(http, provider="openai").complete_json(
            messages=[{"role": "user", "content": "data"}],
            json_schema={"type": "object"},
            schema_name="report",
        )

    assert completion.content == '{"ok":true}'
    assert completion.tool_calls == ()


@pytest.mark.asyncio
async def test_ollama_requests_bounded_json_object():
    async def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        assert payload["response_format"] == {"type": "json_object"}
        assert payload["max_tokens"] == 1_000
        return httpx.Response(
            200,
            json=provider_response(
                message={"role": "assistant", "content": '{"ok":true}'}
            ),
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        completion = await make_provider(http).complete_json(
            messages=[{"role": "user", "content": "data"}],
            json_schema={"type": "object"},
            schema_name="report",
        )

    assert completion.content == '{"ok":true}'


@pytest.mark.asyncio
async def test_provider_retries_retryable_status_then_succeeds():
    requests = 0
    delays = []

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal requests
        requests += 1
        if requests == 1:
            return httpx.Response(503, headers={"retry-after": "0.01"})
        return httpx.Response(
            200,
            json=provider_response(
                message={"role": "assistant", "content": '{"ok":true}'}
            ),
        )

    async def record_sleep(delay: float) -> None:
        delays.append(delay)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        completion = await make_provider(http, sleep=record_sleep).complete_json(
            messages=[{"role": "user", "content": "data"}],
            json_schema={"type": "object"},
            schema_name="report",
        )

    assert completion.attempts == 2
    assert requests == 2
    assert delays == [0.01]


@pytest.mark.asyncio
async def test_provider_rejects_malformed_tool_arguments():
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json=provider_response(
                message={
                    "role": "assistant",
                    "tool_calls": [
                        {
                            "id": "call-1",
                            "function": {
                                "name": "get_run_summary",
                                "arguments": "not-json",
                            },
                        }
                    ],
                }
            ),
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        with pytest.raises(LLMInvalidResponseError, match="malformed tool call"):
            await make_provider(http).choose_tools(
                messages=[{"role": "user", "content": "data"}],
                tools=[{"type": "function", "function": {"name": "tool"}}],
            )


@pytest.mark.asyncio
async def test_provider_stops_after_retry_budget():
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503)

    async def no_sleep(delay: float) -> None:
        return None

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        with pytest.raises(LLMUnavailableError, match="3 attempts"):
            await make_provider(http, sleep=no_sleep).complete_json(
                messages=[{"role": "user", "content": "data"}],
                json_schema={"type": "object"},
                schema_name="report",
            )


@pytest.mark.asyncio
async def test_provider_does_not_retry_local_inference_timeout():
    requests = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal requests
        requests += 1
        raise httpx.ReadTimeout("slow local inference", request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        with pytest.raises(LLMUnavailableError, match="timed out"):
            await make_provider(http).complete_json(
                messages=[{"role": "user", "content": "data"}],
                json_schema={"type": "object"},
                schema_name="report",
            )

    assert requests == 1
