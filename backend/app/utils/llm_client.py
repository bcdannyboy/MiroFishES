"""
LLM client wrapper.
Uses an OpenAI-compatible API interface.
"""

from dataclasses import dataclass
import json
import re
from typing import Optional, Dict, Any, List, Sequence

from pydantic import BaseModel
from openai import OpenAI

from ..config import Config
from .model_routing import TaskModelRouter


@dataclass(frozen=True)
class StructuredLLMResponse:
    """Normalized structured response envelope."""

    response_id: str | None
    model: str | None
    output_text: str
    parsed: Any
    raw_response: Any


class LLMClient:
    """LLM client with additive Responses API support."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        task: str = "default",
        router: TaskModelRouter | None = None,
    ):
        self.router = router or TaskModelRouter()
        route = self._resolve_route(
            task,
            model=model,
            api_key=api_key,
            base_url=base_url,
        )
        self.api_key = route.api_key
        self.base_url = route.base_url
        self.model = route.model

        if not self.api_key:
            raise ValueError("LLM_API_KEY or OPENAI_API_KEY is not configured")

        self.client = OpenAI(
            api_key=self.api_key,
            base_url=self.base_url
        )
        self._client_cache = {
            (self.api_key, self.base_url): self.client,
        }

    def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 4096,
        response_format: Optional[Dict] = None
    ) -> str:
        """
        Send a chat request.
        
        Args:
            messages: Message list
            temperature: Temperature setting
            max_tokens: Maximum token count
            response_format: Response format, such as JSON mode
            
        Returns:
            Model response text
        """
        kwargs = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        
        if response_format:
            kwargs["response_format"] = response_format
        
        response = self.client.chat.completions.create(**kwargs)
        content = response.choices[0].message.content
        return self._clean_text(content)

    def chat_json(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.3,
        max_tokens: int = 4096
    ) -> Dict[str, Any]:
        """
        Send a chat request and return JSON.
        
        Args:
            messages: Message list
            temperature: Temperature setting
            max_tokens: Maximum token count
            
        Returns:
            Parsed JSON object
        """
        response = self.chat(
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            response_format={"type": "json_object"}
        )
        try:
            return json.loads(self._strip_code_fences(response))
        except json.JSONDecodeError:
            raise ValueError(f"LLM returned invalid JSON: {response}")

    def create_response(
        self,
        *,
        messages: Sequence[Dict[str, str]] | None = None,
        input_text: str | None = None,
        instructions: str | None = None,
        task: str = "default",
        model: str | None = None,
        api_key: str | None = None,
        base_url: str | None = None,
        temperature: float | None = None,
        max_output_tokens: int = 4096,
        reasoning: Dict[str, Any] | None = None,
    ) -> StructuredLLMResponse:
        """Send a Responses API call and return normalized text output."""
        route = self.router.resolve(
            task,
        )
        route = self._resolve_route(
            task,
            model=model or route.model,
            api_key=api_key or route.api_key,
            base_url=base_url or route.base_url,
        )
        response_client = self._get_or_create_client(route.api_key, route.base_url)
        response_instructions, response_input = self._build_response_payload(
            messages=messages,
            input_text=input_text,
            instructions=instructions,
        )
        kwargs = {
            "model": route.model,
            "input": response_input,
            "max_output_tokens": max_output_tokens,
        }
        if response_instructions:
            kwargs["instructions"] = response_instructions
        if temperature is not None:
            kwargs["temperature"] = temperature
        if reasoning:
            kwargs["reasoning"] = reasoning

        response = response_client.responses.create(**kwargs)
        output_text = self._clean_text(getattr(response, "output_text", ""))
        return StructuredLLMResponse(
            response_id=getattr(response, "id", None),
            model=getattr(response, "model", route.model),
            output_text=output_text,
            parsed=None,
            raw_response=response,
        )

    def create_structured_response(
        self,
        *,
        schema: type[BaseModel] | Dict[str, Any],
        messages: Sequence[Dict[str, str]] | None = None,
        input_text: str | None = None,
        instructions: str | None = None,
        task: str = "reasoning",
        model: str | None = None,
        api_key: str | None = None,
        base_url: str | None = None,
        temperature: float | None = None,
        max_output_tokens: int = 4096,
        reasoning: Dict[str, Any] | None = None,
    ) -> StructuredLLMResponse:
        """Send a structured Responses API call using a Pydantic model or JSON schema."""
        route = self.router.resolve(
            task,
        )
        route = self._resolve_route(
            task,
            model=model or route.model,
            api_key=api_key or route.api_key,
            base_url=base_url or route.base_url,
        )
        response_client = self._get_or_create_client(route.api_key, route.base_url)
        response_instructions, response_input = self._build_response_payload(
            messages=messages,
            input_text=input_text,
            instructions=instructions,
        )
        kwargs = {
            "model": route.model,
            "input": response_input,
            "max_output_tokens": max_output_tokens,
        }
        if response_instructions:
            kwargs["instructions"] = response_instructions
        if temperature is not None:
            kwargs["temperature"] = temperature
        if reasoning:
            kwargs["reasoning"] = reasoning

        if isinstance(schema, type) and issubclass(schema, BaseModel):
            response = response_client.responses.parse(text_format=schema, **kwargs)
            parsed = getattr(response, "output_parsed", None)
        else:
            response = response_client.responses.create(
                text={"format": schema},
                **kwargs,
            )
            parsed = json.loads(self._strip_code_fences(getattr(response, "output_text", "")))

        output_text = self._clean_text(getattr(response, "output_text", ""))
        return StructuredLLMResponse(
            response_id=getattr(response, "id", None),
            model=getattr(response, "model", route.model),
            output_text=output_text,
            parsed=parsed,
            raw_response=response,
        )

    def _get_or_create_client(self, api_key: str | None, base_url: str) -> OpenAI:
        cache_key = (api_key, base_url)
        if cache_key not in self._client_cache:
            self._client_cache[cache_key] = OpenAI(api_key=api_key, base_url=base_url)
        return self._client_cache[cache_key]

    def _resolve_route(
        self,
        task: str,
        *,
        model: str | None,
        api_key: str | None,
        base_url: str | None,
    ):
        route = self.router.resolve(task)
        return type(route)(
            task=route.task,
            model=model or route.model,
            api_key=api_key or route.api_key,
            base_url=base_url or route.base_url,
        )

    def _build_response_payload(
        self,
        *,
        messages: Sequence[Dict[str, str]] | None,
        input_text: str | None,
        instructions: str | None,
    ) -> tuple[str | None, list[Dict[str, Any]]]:
        response_instructions: list[str] = []
        if instructions:
            response_instructions.append(instructions)

        response_input: list[Dict[str, Any]] = []
        for message in messages or []:
            role = message.get("role", "user")
            content = message.get("content", "")
            if role in {"system", "developer"}:
                if content:
                    response_instructions.append(content)
                continue
            response_input.append(
                {
                    "role": role,
                    "content": [{"type": "input_text", "text": content}],
                }
            )

        if input_text:
            response_input.append(
                {
                    "role": "user",
                    "content": [{"type": "input_text", "text": input_text}],
                }
            )

        return (
            "\n\n".join(part for part in response_instructions if part) or None,
            response_input,
        )

    @staticmethod
    def _clean_text(content: str | None) -> str:
        """Strip known reasoning wrappers from returned text."""
        cleaned_content = (content or "").strip()
        cleaned_content = re.sub(r'<think>[\s\S]*?</think>', '', cleaned_content).strip()
        return cleaned_content

    @classmethod
    def _strip_code_fences(cls, response: str) -> str:
        """Remove Markdown code fences from model JSON payloads."""
        cleaned_response = cls._clean_text(response)
        cleaned_response = re.sub(
            r'^```(?:json)?\s*\n?',
            '',
            cleaned_response,
            flags=re.IGNORECASE,
        )
        cleaned_response = re.sub(r'\n?```\s*$', '', cleaned_response)
        return cleaned_response.strip()
