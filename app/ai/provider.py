"""OpenAI-compatible provider with tool calling and structured output."""

from __future__ import annotations

import asyncio
import json
from collections import deque
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from typing import Any, Protocol

import httpx
from pydantic import ValidationError as PydanticValidationError

from app.ai.errors import LLMInvalidResponseError, LLMUnavailableError
from app.ai.schemas import LLMUsage, RequestedToolCall

RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}
SleepFunction = Callable[[float], Awaitable[None]]
Message = dict[str, Any]


@dataclass(frozen=True, slots=True)
class LLMCompletion:
    """Normalized response envelope independent of one provider."""

    content: str | None
    tool_calls: tuple[RequestedToolCall, ...]
    provider: str
    model: str
    attempts: int
    provider_request_id: str | None
    usage: LLMUsage | None


class LLMProvider(Protocol):
    """Provider operations required by the LangGraph workflow."""

    async def choose_tools(
        self,
        *,
        messages: Sequence[Message],
        tools: Sequence[dict[str, Any]],
    ) -> LLMCompletion: ...

    async def complete_json(
        self,
        *,
        messages: Sequence[Message],
        json_schema: dict[str, Any],
        schema_name: str,
    ) -> LLMCompletion: ...


class OpenAICompatibleLLMProvider:
    """Call `/chat/completions` with bounded retries and strict parsing."""

    def __init__(
        self,
        *,
        http_client: httpx.AsyncClient,
        base_url: str,
        api_key: str | None,
        model: str,
        provider: str,
        max_retries: int = 2,
        backoff_seconds: float = 0.25,
        sleep: SleepFunction = asyncio.sleep,
    ) -> None:
        if not base_url.strip():
            raise ValueError("LLM base URL must not be empty")
        if not model.strip():
            raise ValueError("LLM model must not be empty")
        if not 0 <= max_retries <= 5:
            raise ValueError("LLM max_retries must be between 0 and 5")
        if backoff_seconds < 0:
            raise ValueError("LLM backoff_seconds must not be negative")

        self._http_client = http_client
        self._endpoint = f"{base_url.rstrip('/')}/chat/completions"
        self._api_key = api_key
        self._model = model
        self._provider = provider
        self._max_retries = max_retries
        self._backoff_seconds = backoff_seconds
        self._sleep = sleep

    async def choose_tools(
        self,
        *,
        messages: Sequence[Message],
        tools: Sequence[dict[str, Any]],
    ) -> LLMCompletion:
        """Ask the model to select one or more allowlisted functions."""
        if not tools:
            raise ValueError("At least one tool definition is required")
        payload = {
            "model": self._model,
            "messages": list(messages),
            "temperature": 0,
            "tools": list(tools),
            "tool_choice": "required",
        }
        response, attempts = await self._post(payload)
        return self._normalize_response(
            response, attempts=attempts, require_content=False
        )

    async def complete_json(
        self,
        *,
        messages: Sequence[Message],
        json_schema: dict[str, Any],
        schema_name: str,
    ) -> LLMCompletion:
        """Request one JSON-schema constrained completion."""
        if self._provider.lower() == "ollama":
            response_format: dict[str, Any] = {"type": "json_object"}
        else:
            response_format = {
                "type": "json_schema",
                "json_schema": {
                    "name": schema_name,
                    "strict": True,
                    "schema": json_schema,
                },
            }
        payload = {
            "model": self._model,
            "messages": list(messages),
            "temperature": 0,
            "max_tokens": 1_000,
            "response_format": response_format,
        }
        response, attempts = await self._post(payload)
        return self._normalize_response(
            response, attempts=attempts, require_content=True
        )

    async def _post(self, payload: dict[str, Any]) -> tuple[httpx.Response, int]:
        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"

        total_attempts = self._max_retries + 1
        for attempt in range(1, total_attempts + 1):
            try:
                response = await self._http_client.post(
                    self._endpoint,
                    json=payload,
                    headers=headers,
                )
            except httpx.TimeoutException as exc:
                raise LLMUnavailableError(
                    "LLM request timed out; local inference is not retried"
                ) from exc
            except httpx.TransportError as exc:
                if attempt < total_attempts:
                    await self._sleep(self._retry_delay(attempt))
                    continue
                raise LLMUnavailableError(
                    f"LLM provider is unavailable after {attempt} attempts"
                ) from exc

            if response.status_code in RETRYABLE_STATUS_CODES:
                if attempt < total_attempts:
                    await self._sleep(self._retry_delay(attempt, response=response))
                    continue
                raise LLMUnavailableError(
                    "LLM provider remained unavailable after "
                    f"{attempt} attempts (HTTP {response.status_code})"
                )
            if response.is_error:
                raise LLMUnavailableError(
                    f"LLM provider rejected the request (HTTP {response.status_code})"
                )
            return response, attempt

        raise AssertionError("unreachable")

    def _normalize_response(
        self,
        response: httpx.Response,
        *,
        attempts: int,
        require_content: bool,
    ) -> LLMCompletion:
        try:
            payload = response.json()
            message = payload["choices"][0]["message"]
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            raise LLMInvalidResponseError(
                "LLM provider returned an unexpected response envelope"
            ) from exc

        content_raw = message.get("content")
        content = content_raw if isinstance(content_raw, str) else None
        if require_content and (content is None or not content.strip()):
            raise LLMInvalidResponseError(
                "LLM provider returned empty structured output"
            )

        tool_calls = self._normalize_tool_calls(message.get("tool_calls", []))
        if not require_content and not tool_calls:
            raise LLMInvalidResponseError("LLM provider selected no tools")

        usage: LLMUsage | None = None
        if payload.get("usage") is not None:
            try:
                usage = LLMUsage.model_validate(payload["usage"])
            except PydanticValidationError as exc:
                raise LLMInvalidResponseError(
                    "LLM provider returned invalid token usage metadata"
                ) from exc

        request_id = response.headers.get("x-request-id") or payload.get("id")
        return LLMCompletion(
            content=content,
            tool_calls=tool_calls,
            provider=self._provider,
            model=str(payload.get("model") or self._model),
            attempts=attempts,
            provider_request_id=str(request_id) if request_id else None,
            usage=usage,
        )

    def _normalize_tool_calls(self, payload: Any) -> tuple[RequestedToolCall, ...]:
        if payload in (None, []):
            return ()
        if not isinstance(payload, list):
            raise LLMInvalidResponseError("tool_calls must be an array")

        normalized: list[RequestedToolCall] = []
        for position, item in enumerate(payload, 1):
            try:
                function = item["function"]
                name = function["name"]
                arguments_raw = function.get("arguments", {})
                if isinstance(arguments_raw, str):
                    arguments = json.loads(arguments_raw)
                else:
                    arguments = arguments_raw
                if not isinstance(arguments, dict):
                    raise TypeError("arguments are not an object")
                normalized.append(
                    RequestedToolCall(
                        call_id=str(item.get("id") or f"call_{position}"),
                        tool_name=str(name),
                        arguments=arguments,
                    )
                )
            except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
                raise LLMInvalidResponseError(
                    "LLM provider returned a malformed tool call"
                ) from exc
        return tuple(normalized)

    def _retry_delay(
        self,
        attempt: int,
        *,
        response: httpx.Response | None = None,
    ) -> float:
        if response is not None:
            retry_after = response.headers.get("retry-after")
            if retry_after is not None:
                try:
                    return min(max(float(retry_after), 0), 5.0)
                except ValueError:
                    pass
        return min(self._backoff_seconds * (2 ** (attempt - 1)), 5.0)


class StubLLMProvider:
    """Programmable provider for graph tests and offline CI."""

    def __init__(
        self,
        *,
        tool_batches: Sequence[Sequence[RequestedToolCall]],
        json_responses: Sequence[str],
    ) -> None:
        self._tool_batches = deque(tuple(batch) for batch in tool_batches)
        self._json_responses = deque(json_responses)
        self.calls: list[dict[str, Any]] = []

    def enqueue_json_response(self, content: str) -> None:
        """Append a response after fixture-specific evidence ids are known."""
        self._json_responses.append(content)

    async def choose_tools(
        self,
        *,
        messages: Sequence[Message],
        tools: Sequence[dict[str, Any]],
    ) -> LLMCompletion:
        self.calls.append(
            {
                "operation": "choose_tools",
                "messages": list(messages),
                "tools": list(tools),
            }
        )
        if not self._tool_batches:
            raise AssertionError("Stub has no tool response left")
        return self._completion(tool_calls=self._tool_batches.popleft())

    async def complete_json(
        self,
        *,
        messages: Sequence[Message],
        json_schema: dict[str, Any],
        schema_name: str,
    ) -> LLMCompletion:
        self.calls.append(
            {
                "operation": "complete_json",
                "messages": list(messages),
                "json_schema": json_schema,
                "schema_name": schema_name,
            }
        )
        if not self._json_responses:
            raise AssertionError("Stub has no JSON response left")
        return self._completion(content=self._json_responses.popleft())

    @staticmethod
    def _completion(
        *,
        content: str | None = None,
        tool_calls: Sequence[RequestedToolCall] = (),
    ) -> LLMCompletion:
        return LLMCompletion(
            content=content,
            tool_calls=tuple(tool_calls),
            provider="stub",
            model="stub-model",
            attempts=1,
            provider_request_id="stub-request",
            usage=LLMUsage(
                prompt_tokens=10,
                completion_tokens=5,
                total_tokens=15,
            ),
        )


def strip_markdown_fence(content: str) -> str:
    """Accept providers that wrap otherwise valid JSON in one code fence."""
    stripped = content.strip()
    if not stripped.startswith("```"):
        return stripped
    lines = stripped.splitlines()
    if len(lines) >= 3 and lines[-1].strip() == "```":
        return "\n".join(lines[1:-1]).strip()
    return stripped
