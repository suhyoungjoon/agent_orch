import json
from app.core.config import settings
from app.models.intent import AgentConfig, ParseIntentResponse

_MOCK_RESPONSE = ParseIntentResponse(
    agents=[
        AgentConfig(
            name="ResearchAgent",
            role="researcher",
            goal="주어진 주제에 대해 심층적인 정보를 수집하고 분석합니다.",
            tools=["web_search", "document_reader"],
            execution_order=1,
        ),
        AgentConfig(
            name="WriterAgent",
            role="writer",
            goal="수집된 정보를 바탕으로 명확하고 구조화된 보고서를 작성합니다.",
            tools=["text_editor"],
            execution_order=2,
        ),
    ],
    raw_input="",
    is_mock=True,
)

_SYSTEM_PROMPT = """You are an AI agent configuration assistant.
Given a user's natural language request, output a JSON configuration for a multi-agent workflow.

Output a JSON object with this exact schema:
{
  "agents": [
    {
      "name": "string (PascalCase agent name)",
      "role": "string (one of: researcher, writer, analyst, coder)",
      "goal": "string (specific goal for this agent in Korean)",
      "tools": ["array of tool names this agent needs"],
      "execution_order": integer (1-based, sequential execution order)
    }
  ]
}

Rules:
- Decompose the task into 2-4 specialized agents
- Each agent has a single, focused responsibility
- Execution order must be sequential (1, 2, 3, ...)
- Tools should be relevant to the role: researcher→[web_search, document_reader], writer→[text_editor], analyst→[data_analyzer, chart_generator], coder→[code_executor, file_manager]
- Write goals in Korean
- Respond ONLY with valid JSON, no extra text"""


async def parse_intent(text: str) -> ParseIntentResponse:
    if not settings.anthropic_api_key:
        mock = _MOCK_RESPONSE.model_copy(deep=True)
        mock.raw_input = text
        return mock

    return await _call_claude(text)


async def _call_claude(text: str) -> ParseIntentResponse:
    import anthropic

    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

    response = await client.messages.create(
        model="claude-opus-4-7",
        max_tokens=2048,
        thinking={"type": "adaptive"},
        system=_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": text}],
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
        model_used="claude-opus-4-7",
        is_mock=False,
    )
