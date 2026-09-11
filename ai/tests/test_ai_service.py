from __future__ import annotations

import pytest

from ai.providers.openai_provider import OpenAIProvider


@pytest.mark.asyncio
async def test_openai_provider_parse_json(monkeypatch):
    provider = OpenAIProvider(api_key="test", model="test-model")
    payload = '{"skills":["python"],"budget":"$3k","difficulty":"medium","seniority":"mid","urgency":"high","timezone":"UTC","project_type":"contract","relevance_score":0.85,"success_probability":0.7,"estimated_hours":120.0,"estimated_profit":5000.0,"missing_skills":["docker"],"risk_score":0.3,"summary":"Clean summary.","proposal_draft":"Draft.","questions_to_ask":["What is the deadline?"]}'

    result = provider._parse_json(payload)
    assert isinstance(result, dict)
    assert result["skills"] == ["python"]
