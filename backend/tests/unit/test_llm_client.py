import importlib
from types import SimpleNamespace

from pydantic import BaseModel


class _ExtractionResult(BaseModel):
    verdict: str
    confidence: float


class _FakeChatCompletions:
    def __init__(self):
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(
                        content='<think>hidden reasoning</think>\n```json\n{"ok": true}\n```'
                    )
                )
            ]
        )


class _FakeResponses:
    def __init__(self):
        self.parse_calls = []

    def parse(self, **kwargs):
        self.parse_calls.append(kwargs)
        return SimpleNamespace(
            id="resp_test_123",
            model=kwargs["model"],
            output_text='{"verdict":"supported","confidence":0.82}',
            output_parsed=_ExtractionResult(verdict="supported", confidence=0.82),
            usage={"input_tokens": 12, "output_tokens": 7},
        )


class _FakeOpenAI:
    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs
        self.chat = SimpleNamespace(completions=_FakeChatCompletions())
        self.responses = _FakeResponses()


class _RouterStub:
    def resolve(self, task):
        return SimpleNamespace(
            task=task,
            model={
                "default": "gpt-4o-mini",
                "reasoning": "gpt-5-mini",
            }[task],
            api_key="test-key",
            base_url="https://openai.example/v1",
        )


def test_chat_json_preserves_chat_completion_compatibility(monkeypatch):
    module = importlib.import_module("app.utils.llm_client")
    monkeypatch.setattr(module, "OpenAI", _FakeOpenAI)

    client = module.LLMClient(api_key="test-key", base_url="https://openai.example/v1")
    result = client.chat_json([{"role": "user", "content": "Return JSON"}])

    assert result == {"ok": True}
    assert client.client.chat.completions.calls[0]["response_format"] == {
        "type": "json_object"
    }


def test_create_structured_response_uses_responses_parse_and_task_routing(monkeypatch):
    module = importlib.import_module("app.utils.llm_client")
    monkeypatch.setattr(module, "OpenAI", _FakeOpenAI)

    client = module.LLMClient(router=_RouterStub())
    response = client.create_structured_response(
        messages=[
            {"role": "system", "content": "Extract only the requested fields."},
            {"role": "user", "content": "Claim: demand is rising."},
        ],
        schema=_ExtractionResult,
        task="reasoning",
        reasoning={"effort": "medium"},
        max_output_tokens=200,
    )

    parse_call = client.client.responses.parse_calls[0]

    assert parse_call["model"] == "gpt-5-mini"
    assert parse_call["instructions"] == "Extract only the requested fields."
    assert parse_call["input"] == [
        {
            "role": "user",
            "content": [{"type": "input_text", "text": "Claim: demand is rising."}],
        }
    ]
    assert parse_call["reasoning"] == {"effort": "medium"}
    assert response.response_id == "resp_test_123"
    assert response.model == "gpt-5-mini"
    assert response.output_text == '{"verdict":"supported","confidence":0.82}'
    assert response.parsed == _ExtractionResult(verdict="supported", confidence=0.82)
