"""The model behind the agent, behind a small protocol so tests and CI never need a key.

    AnthropicClient   the real Claude API (prompt caching, timeouts, limited retries, refusal
                      fallback)
    ScriptedClient    replays prepared responses (unit tests, CI)

Responses are plain JSON content blocks (dicts), exactly as the API returned them, so the
transcript can be stored and replayed unchanged: Claude Sonnet 5.5 binds thinking blocks to the
conversation that produced them, so history is append-only and blocks go back as they came.
"""

import itertools
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol

Block = dict[str, Any]
Message = dict[str, Any]

Rates = tuple[float, float, float, float]

# USD per million tokens: input, output, cache read, 5-minute cache write.
PRICES: dict[str, Rates] = {
    "claude-sonnet-5-5": (2.00, 10.00, 0.20, 2.50),
    "claude-haiku-5-5": (0.10, 0.50, 0.01, 0.125),
}
# A request whose prompt (input + cache read + cache write) is over LONG_PROMPT_TOKENS pays
# these instead, for all of its tokens (Haiku 5.5; the pricing page, checked 2026-10-20).
LONG_PROMPT_TOKENS = 100_000
LONG_PROMPT_PRICES: dict[str, Rates] = {
    "claude-haiku-5-5": (0.50, 2.50, 0.05, 0.625),
}

FALLBACK_BETA = "server-side-fallback-2026-07-01"
# The models that accept `fallbacks: "default"`. Haiku 5.5 has no server-side fallback (a
# declined request stays declined), so it gets neither the beta nor the parameter.
SERVER_FALLBACK_MODELS = frozenset({"claude-sonnet-5-5", "claude-opus-5-5", "claude-opus-5"})


@dataclass(frozen=True)
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_input_tokens: int = 0
    cache_creation_input_tokens: int = 0

    def __add__(self, other: "Usage") -> "Usage":
        return Usage(
            self.input_tokens + other.input_tokens,
            self.output_tokens + other.output_tokens,
            self.cache_read_input_tokens + other.cache_read_input_tokens,
            self.cache_creation_input_tokens + other.cache_creation_input_tokens,
        )

    @property
    def prompt_tokens(self) -> int:
        return self.input_tokens + self.cache_read_input_tokens + self.cache_creation_input_tokens

    def cost_usd(self, model: str) -> float | None:
        """Estimated cost of ONE request's usage (the rate can depend on the request's prompt
        length: use requests_cost_usd for several); None for a model without a price entry."""
        prices = PRICES.get(model)
        if prices is None:
            return None
        if self.prompt_tokens > LONG_PROMPT_TOKENS:
            prices = LONG_PROMPT_PRICES.get(model, prices)
        input_price, output_price, read_price, write_price = prices
        return (
            self.input_tokens * input_price
            + self.output_tokens * output_price
            + self.cache_read_input_tokens * read_price
            + self.cache_creation_input_tokens * write_price
        ) / 1_000_000


def requests_cost_usd(requests: Iterable[Usage], model: str) -> float | None:
    """Estimated cost of several requests, each priced on its own; None without a price entry."""
    if model not in PRICES:
        return None
    return sum(usage.cost_usd(model) or 0.0 for usage in requests)


@dataclass(frozen=True)
class LLMResponse:
    content: list[Block]
    stop_reason: str  # end_turn | tool_use | max_tokens | refusal | pause_turn | ...
    usage: Usage = field(default_factory=Usage)
    model: str = ""
    request_id: str | None = None

    @property
    def text(self) -> str:
        return "".join(b.get("text", "") for b in self.content if b.get("type") == "text").strip()

    @property
    def tool_uses(self) -> list[Block]:
        return [b for b in self.content if b.get("type") == "tool_use"]


ErrorKind = Literal["timeout", "connection", "rate_limit", "server", "auth", "bad_request", "other"]


class LLMError(Exception):
    """The model call failed. `kind` says why; the message never contains the API key."""

    def __init__(self, kind: ErrorKind, message: str) -> None:
        self.kind = kind
        super().__init__(f"{kind}: {message}")


ToolChoice = dict[str, Any]


class LLMClient(Protocol):
    model: str

    def create(
        self,
        *,
        messages: Sequence[Message],
        tools: Sequence[dict[str, Any]],
        system: str,
        tool_choice: ToolChoice | None = None,
    ) -> LLMResponse: ...


# --- the real API -----------------------------------------------------------------------------


class AnthropicClient:
    """Claude via the official SDK.

    - Caching: a breakpoint on the system prompt caches the tools with it (render order is
      tools -> system -> messages), and top-level automatic caching covers the conversation.
    - Adaptive thinking (the default) at `effort`; thinking blocks are returned untouched.
    - Server-side refusal fallback (`fallbacks: "default"`, SERVER_FALLBACK_MODELS only): a
      declined request is re-run on
      Anthropic's recommended fallback model inside the same call.
    - The SDK retries connection errors, 408/409/429 and 5xx `max_retries` times with backoff.
    """

    def __init__(
        self,
        api_key: str,
        model: str,
        *,
        effort: str = "low",
        max_tokens: int = 16_000,
        timeout_seconds: float = 60.0,
        max_retries: int = 2,
        sdk_client: Any = None,  # tests inject a fake
    ) -> None:
        if sdk_client is None:
            import anthropic

            sdk_client = anthropic.Anthropic(
                api_key=api_key, timeout=timeout_seconds, max_retries=max_retries
            )
        self._sdk = sdk_client
        self.model = model
        self.effort = effort
        self.max_tokens = max_tokens

    def request(
        self,
        messages: Sequence[Message],
        tools: Sequence[dict[str, Any]],
        system: str,
        tool_choice: ToolChoice | None,
    ) -> dict[str, Any]:
        """The request parameters (exposed for tests)."""
        params: dict[str, Any] = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "system": [{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
            "tools": list(tools),
            "messages": list(messages),
            "cache_control": {"type": "ephemeral"},
            "output_config": {"effort": self.effort},
        }
        if self.model in SERVER_FALLBACK_MODELS:
            params["betas"] = [FALLBACK_BETA]
            params["fallbacks"] = "default"
        if tool_choice is not None:
            params["tool_choice"] = tool_choice
        return params

    def create(
        self,
        *,
        messages: Sequence[Message],
        tools: Sequence[dict[str, Any]],
        system: str,
        tool_choice: ToolChoice | None = None,
    ) -> LLMResponse:
        import anthropic

        try:
            response = self._sdk.beta.messages.create(
                **self.request(messages, tools, system, tool_choice)
            )
        except anthropic.APITimeoutError as error:
            raise LLMError("timeout", "the model did not answer in time") from error
        except anthropic.APIConnectionError as error:
            raise LLMError("connection", "could not reach the API") from error
        except anthropic.RateLimitError as error:
            raise LLMError("rate_limit", "rate limited") from error
        except (anthropic.AuthenticationError, anthropic.PermissionDeniedError) as error:
            raise LLMError("auth", "the API key was rejected") from error
        except anthropic.BadRequestError as error:
            raise LLMError("bad_request", str(error.message)) from error
        except anthropic.APIStatusError as error:
            kind: ErrorKind = "server" if error.status_code >= 500 else "other"
            raise LLMError(kind, f"HTTP {error.status_code}") from error
        usage = response.usage
        return LLMResponse(
            content=[block.to_dict() for block in response.content],
            stop_reason=response.stop_reason or "",
            usage=Usage(
                input_tokens=usage.input_tokens or 0,
                output_tokens=usage.output_tokens or 0,
                cache_read_input_tokens=getattr(usage, "cache_read_input_tokens", 0) or 0,
                cache_creation_input_tokens=getattr(usage, "cache_creation_input_tokens", 0) or 0,
            ),
            model=response.model,
            request_id=getattr(response, "_request_id", None),
        )


# --- scripted (tests, CI) ---------------------------------------------------------------------

ScriptStep = LLMResponse | LLMError | Callable[[Sequence[Message]], LLMResponse]


@dataclass
class ScriptedCall:
    messages: list[Message]
    tools: list[dict[str, Any]]
    system: str
    tool_choice: ToolChoice | None


class ScriptExhausted(AssertionError):
    pass


class ScriptedClient:
    """Replays `steps` in order: a response, an error to raise, or a function of the messages.

    Every call is recorded in `calls` (a deep copy of what the model would have seen).
    """

    def __init__(self, steps: Sequence[ScriptStep], model: str = "scripted") -> None:
        self._steps = list(steps)
        self.calls: list[ScriptedCall] = []
        self.model = model

    def create(
        self,
        *,
        messages: Sequence[Message],
        tools: Sequence[dict[str, Any]],
        system: str,
        tool_choice: ToolChoice | None = None,
    ) -> LLMResponse:
        import copy

        self.calls.append(
            ScriptedCall(copy.deepcopy(list(messages)), list(tools), system, tool_choice)
        )
        if not self._steps:
            raise ScriptExhausted(f"no scripted response left for call {len(self.calls)}")
        step = self._steps.pop(0)
        if isinstance(step, LLMError):
            raise step
        if callable(step):
            return step(messages)
        return step

    @property
    def remaining(self) -> int:
        return len(self._steps)


def text_response(text: str, usage: Usage | None = None) -> LLMResponse:
    return LLMResponse(
        content=[{"type": "text", "text": text}], stop_reason="end_turn", usage=usage or Usage()
    )


_TOOL_IDS = itertools.count(1)


def tool_response(*calls: tuple[str, dict[str, Any]], text: str = "") -> LLMResponse:
    """A response that calls tools; each call gets a fresh id (toolu_<name>_<n>)."""
    content: list[Block] = []
    if text:
        content.append({"type": "text", "text": text})
    for name, tool_input in calls:
        tool_id = f"toolu_{name}_{next(_TOOL_IDS)}"
        content.append({"type": "tool_use", "id": tool_id, "name": name, "input": tool_input})
    return LLMResponse(content=content, stop_reason="tool_use")
