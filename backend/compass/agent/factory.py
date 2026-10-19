"""Build the agent for a configuration: the scripted demo model (COMPASS_LLM=scripted), Claude
when a key is set, otherwise the null runner."""

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
        max_session_turns=settings.max_session_turns,
        max_session_input_tokens=settings.max_session_input_tokens,
        # demo mode's scripted model costs nothing; live mode stops at the daily cap
        daily_spend_cap_usd=None if settings.llm == "scripted" else settings.daily_spend_cap_usd,
        guard=make_guard(services.store),
        template=make_template(services.store),
        background=background,
    )


def build_agent(settings: Settings, services: Services, tool_runner: ToolRunner) -> AgentRunner:
    if settings.llm == "scripted":  # demo mode: only the model is scripted
        from compass.agent.demo_llm import DemoClient

        return build_claude_runner(settings, services, llm=DemoClient(), tool_runner=tool_runner)
    if not settings.anthropic_api_key:
        return NullAgentRunner()
    return build_claude_runner(settings, services, tool_runner=tool_runner)
