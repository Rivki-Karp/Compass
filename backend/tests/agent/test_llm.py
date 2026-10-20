"""The LLM client layer: request shape, error mapping, usage and cost. No network, no key."""

from types import SimpleNamespace
from typing import Any

import anthropic
import httpx2
import pytest

from compass.agent.llm import (
    FALLBACK_BETA,
    AnthropicClient,
    LLMError,
    LLMResponse,
    ScriptedClient,
    ScriptExhausted,
    Usage,
    requests_cost_usd,
    text_response,
    tool_response,
)

TOOLS = [{"name": "get_rule", "description": "d", "input_schema": {"type": "object"}}]
MESSAGES = [{"role": "user", "content": "שלום"}]


class FakeBlock:
    def __init__(self, data: dict[str, Any]) -> None:
        self._data = data

    def to_dict(self) -> dict[str, Any]:
        return dict(self._data)


class FakeSDK:
    """Stands in for anthropic.Anthropic(): records the request, returns or raises."""

    def __init__(self, result: Any) -> None:
        self.requests: list[dict[str, Any]] = []
        self._result = result
        self.beta = SimpleNamespace(messages=SimpleNamespace(create=self._create))

    def _create(self, **params: Any) -> Any:
        self.requests.append(params)
        if isinstance(self._result, Exception):
            raise self._result
        return self._result


def _api_response() -> Any:
    return SimpleNamespace(
        content=[
            FakeBlock({"type": "thinking", "thinking": "", "signature": "sig"}),
            FakeBlock({"type": "text", "text": "שלום!"}),
        ],
        stop_reason="end_turn",
        usage=SimpleNamespace(
            input_tokens=100,
            output_tokens=50,
            cache_read_input_tokens=4000,
            cache_creation_input_tokens=0,
        ),
        model="claude-sonnet-5-5",
        _request_id="req_1",
    )


def _client(result: Any) -> tuple[AnthropicClient, FakeSDK]:
    sdk = FakeSDK(result)
    return AnthropicClient("sk-ant-test", "claude-sonnet-5-5", sdk_client=sdk), sdk


def test_request_shape() -> None:
    client, sdk = _client(_api_response())
    response = client.create(messages=MESSAGES, tools=TOOLS, system="אתה יועץ")
    (params,) = sdk.requests
    assert params["model"] == "claude-sonnet-5-5"
    assert params["system"] == [
        {"type": "text", "text": "אתה יועץ", "cache_control": {"type": "ephemeral"}}
    ]
    assert params["cache_control"] == {"type": "ephemeral"}  # conversation prefix
    assert params["tools"] == TOOLS and params["messages"] == MESSAGES
    assert params["output_config"] == {"effort": "low"}
    assert params["betas"] == [FALLBACK_BETA] and params["fallbacks"] == "default"
    assert "tool_choice" not in params and "thinking" not in params  # adaptive by default
    assert response.text == "שלום!"
    assert response.content[0] == {"type": "thinking", "thinking": "", "signature": "sig"}
    assert response.request_id == "req_1"


def test_haiku_gets_no_server_side_fallback() -> None:
    # Haiku 5.5 has no server-side fallback: neither the beta nor the parameter is sent.
    sdk = FakeSDK(_api_response())
    client = AnthropicClient("sk-ant-test", "claude-haiku-5-5", effort="medium", sdk_client=sdk)
    client.create(messages=MESSAGES, tools=TOOLS, system="s")
    (params,) = sdk.requests
    assert params["model"] == "claude-haiku-5-5"
    assert params["output_config"] == {"effort": "medium"}
    assert params["cache_control"] == {"type": "ephemeral"}
    assert "betas" not in params and "fallbacks" not in params


def test_tool_choice_none_is_passed() -> None:
    client, sdk = _client(_api_response())
    client.create(messages=MESSAGES, tools=TOOLS, system="s", tool_choice={"type": "none"})
    assert sdk.requests[0]["tool_choice"] == {"type": "none"}


def _status_error(cls: type[anthropic.APIStatusError], status: int) -> Exception:
    request = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")
    response = httpx2.Response(status, request=request)
    return cls("boom", response=response, body=None)


@pytest.mark.parametrize(
    ("error", "kind"),
    [
        (anthropic.APITimeoutError(request=httpx2.Request("POST", "https://x")), "timeout"),
        (anthropic.APIConnectionError(request=httpx2.Request("POST", "https://x")), "connection"),
        (_status_error(anthropic.RateLimitError, 429), "rate_limit"),
        (_status_error(anthropic.AuthenticationError, 401), "auth"),
        (_status_error(anthropic.InternalServerError, 500), "server"),
        (_status_error(anthropic.BadRequestError, 400), "bad_request"),
    ],
)
def test_errors_are_mapped(error: Exception, kind: str) -> None:
    client, _ = _client(error)
    with pytest.raises(LLMError) as exc_info:
        client.create(messages=MESSAGES, tools=TOOLS, system="s")
    assert exc_info.value.kind == kind
    assert "sk-ant-test" not in str(exc_info.value)


def test_usage_and_cost() -> None:
    usage = Usage(1_000_000, 100_000, 2_000_000, 200_000)
    # $2 input + $1 output + $0.40 cache read + $0.50 cache write
    assert usage.cost_usd("claude-sonnet-5-5") == pytest.approx(3.90)
    assert usage.cost_usd("unknown-model") is None


def test_haiku_cost_depends_on_the_prompt_length() -> None:
    # Up to 100K prompt tokens (input + cache read + cache write): $0.10 / $0.50 / $0.01 / $0.125
    short = Usage(10_000, 1_000, 80_000, 10_000)
    assert short.prompt_tokens == 100_000
    assert short.cost_usd("claude-haiku-5-5") == pytest.approx(0.001 + 0.0005 + 0.0008 + 0.00125)
    # Over 100K: every token of that request at $0.50 / $2.50 / $0.05 / $0.625
    long = Usage(10_001, 1_000, 80_000, 10_000)
    assert long.cost_usd("claude-haiku-5-5") == pytest.approx(0.0050005 + 0.0025 + 0.004 + 0.00625)
    # Several requests are priced one by one, never as one long prompt.
    assert requests_cost_usd([short, short], "claude-haiku-5-5") == pytest.approx(0.0071)
    assert (short + short).cost_usd("claude-haiku-5-5") != pytest.approx(0.0071)
    assert requests_cost_usd([short], "unknown-model") is None
    assert requests_cost_usd([], "claude-sonnet-5-5") == 0
    assert (Usage(1, 2, 3, 4) + Usage(10, 20, 30, 40)) == Usage(11, 22, 33, 44)


def test_scripted_client_replays_and_records() -> None:
    def echo(messages: Any) -> LLMResponse:
        return text_response(f"{len(messages)} messages")

    scripted = ScriptedClient([tool_response(("get_rule", {"topic": "budgets"})), echo])
    first = scripted.create(messages=MESSAGES, tools=TOOLS, system="s")
    assert first.stop_reason == "tool_use"
    assert first.tool_uses[0]["name"] == "get_rule"
    assert scripted.create(messages=MESSAGES * 3, tools=TOOLS, system="s").text == "3 messages"
    assert len(scripted.calls) == 2 and scripted.calls[0].system == "s"
    with pytest.raises(ScriptExhausted):
        scripted.create(messages=MESSAGES, tools=TOOLS, system="s")


def test_scripted_errors_and_unique_ids() -> None:
    scripted = ScriptedClient([LLMError("timeout", "slow")])
    with pytest.raises(LLMError, match="timeout"):
        scripted.create(messages=MESSAGES, tools=TOOLS, system="s")
    a = tool_response(("compare", {}), ("compare", {})).tool_uses
    b = tool_response(("compare", {})).tool_uses
    ids = [u["id"] for u in a + b]
    assert len(set(ids)) == 3
