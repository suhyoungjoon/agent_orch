import json
from typing import TYPE_CHECKING
from app.core.config import settings
from app.models.intent import AgentConfig, ParseIntentResponse

if TYPE_CHECKING:
    from app.db.models.agent_orm import AgentORM

_SYSTEM_PROMPT = """You are an AI agent configuration assistant.
Given a user's natural language request and a list of existing agents in the registry, output a JSON configuration for a multi-agent workflow.

Output a JSON object with this exact schema:
{
  "agents": [
    {
      "name": "string (PascalCase agent name)",
      "role": "string (one of: researcher, writer, analyst, coder)",
      "goal": "string (specific goal for this agent in Korean)",
      "tools": ["array of tool names this agent needs"],
      "execution_order": integer (1-based, sequential execution order),
      "existing_agent_id": "string or null (ID of matching existing agent, null if none matches)"
    }
  ]
}

Rules:
- Decompose the task into 2-4 specialized agents
- Each agent has a single, focused responsibility
- Execution order must be sequential (1, 2, 3, ...)
- If an existing agent in the registry closely matches the required role and goal, set existing_agent_id to that agent's id and use its name
- Only set existing_agent_id when the match is strong (same role, similar goal)
- Tools should be relevant to the role: researcher→[web_search, document_reader], writer→[text_editor], analyst→[data_analyzer, chart_generator], coder→[code_executor, file_manager]
- Write goals in Korean
- Respond ONLY with valid JSON, no extra text"""


def _build_registry_context(existing_agents: "list[AgentORM]") -> str:
    if not existing_agents:
        return "Registry is empty."
    lines = ["Existing agents in registry:"]
    for a in existing_agents:
        lines.append(f"- id={a.id}, name={a.name}, role={a.role}, goal={a.goal[:80]}")
    return "\n".join(lines)


async def parse_intent(text: str, existing_agents: "list[AgentORM] | None" = None) -> ParseIntentResponse:
    agents_list = existing_agents or []

    if not settings.anthropic_api_key:
        return _mock_response(text, agents_list)

    return await _call_claude(text, agents_list)


def _mock_response(text: str, existing_agents: "list[AgentORM]") -> ParseIntentResponse:
    researcher_id = next((a.id for a in existing_agents if a.role == "researcher"), None)
    writer_id = next((a.id for a in existing_agents if a.role == "writer"), None)

    return ParseIntentResponse(
        agents=[
            AgentConfig(
                name=next((a.name for a in existing_agents if a.role == "researcher"), "ResearchAgent"),
                role="researcher",
                goal="주어진 주제에 대해 심층적인 정보를 수집하고 분석합니다.",
                tools=["web_search", "document_reader"],
                execution_order=1,
                existing_agent_id=researcher_id,
            ),
            AgentConfig(
                name=next((a.name for a in existing_agents if a.role == "writer"), "WriterAgent"),
                role="writer",
                goal="수집된 정보를 바탕으로 명확하고 구조화된 보고서를 작성합니다.",
                tools=["text_editor"],
                execution_order=2,
                existing_agent_id=writer_id,
            ),
        ],
        raw_input=text,
        is_mock=True,
    )


async def _call_claude(text: str, existing_agents: "list[AgentORM]") -> ParseIntentResponse:
    import anthropic

    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
    registry_context = _build_registry_context(existing_agents)

    response = await client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2048,
        system=_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": f"{registry_context}\n\nUser request: {text}"}],
    )

    content_text = next(
        (block.text for block in response.content if hasattr(block, "text")),
        "{}",
    )
    data = json.loads(content_text)

    agents = [AgentConfig(**a) for a in data.get("agents", [])]
    return ParseIntentResponse(
        agents=agents,
        raw_input=text,
        model_used="claude-sonnet-4-6",
        is_mock=False,
    )
