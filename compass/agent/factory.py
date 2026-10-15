"""Build the agent for a configuration: Claude when a key is set, otherwise the null runner."""

from compass.agent.llm import AnthropicClient, LLMClient
from compass.agent.prompts import load_system_prompt
from compass.agent.runner import ClaudeAgentRunner
from compass.api.agent import AgentRunner, NullAgentRunner
from compass.api.settings import Settings
from compass.tools import ToolRunner
from compass.tools.services import Services


def build_claude_runner(
    settings: Settings,
    services: Services,
    *,
    llm: LLMClient | None = None,
    tool_runner: ToolRunner | None = None,
    background: bool = True,
) -> ClaudeAgentRunner:
    if llm is None:
        assert settings.anthropic_api_key, "ANTHROPIC_API_KEY is not set"
        llm = AnthropicClient(settings.anthropic_api_key, settings.model)
    from compass.agent.guard import make_guard
    from compass.agent.templates import make_template

    return ClaudeAgentRunner(
        services,
        llm,
        load_system_prompt(),
        tool_runner=tool_runner,
        max_tool_rounds=settings.max_tool_rounds,
        guard=make_guard(services.store),
        template=make_template(services.store),
        background=background,
    )


def build_agent(settings: Settings, services: Services, tool_runner: ToolRunner) -> AgentRunner:
    if not settings.anthropic_api_key:
        return NullAgentRunner()
    return build_claude_runner(settings, services, tool_runner=tool_runner)
