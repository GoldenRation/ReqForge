"""Base Agent class wrapping Anthropic SDK with retry and structured output."""

import json
import time
from typing import Optional

import anthropic

from src.config import get_api_key, get_model, get_base_url, MAX_RETRIES, TEMPERATURE, MAX_TOKENS


class AgentError(Exception):
    pass


class BaseAgent:
    """Foundation for all specialized agents in the pipeline."""

    role_name: str = "base"
    system_prompt: str = ""

    def __init__(self, model: Optional[str] = None):
        api_key = get_api_key()
        if not api_key:
            raise AgentError(
                "API Key not set. Create a .env file, set the environment variable, "
                "or configure it in the Settings panel of the web UI."
            )
        base_url = get_base_url()
        client_kwargs = {"api_key": api_key}
        if base_url:
            client_kwargs["base_url"] = base_url
        self.client = anthropic.Anthropic(**client_kwargs)
        self.model = model or get_model()

    def _call(
        self,
        user_message: str,
        system_prompt: Optional[str] = None,
        temperature: float = TEMPERATURE,
        max_tokens: int = MAX_TOKENS,
    ) -> str:
        """Call Claude with retry logic. Returns raw text response."""
        system = system_prompt or self.system_prompt
        last_error = None

        for attempt in range(MAX_RETRIES):
            try:
                response = self.client.messages.create(
                    model=self.model,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    system=system,
                    messages=[{"role": "user", "content": user_message}],
                )
                return response.content[0].text

            except anthropic.RateLimitError as e:
                last_error = e
                wait = 2 ** attempt
                time.sleep(wait)

            except anthropic.APIError as e:
                last_error = e
                if attempt < MAX_RETRIES - 1:
                    time.sleep(1)

        raise AgentError(f"Agent '{self.role_name}' failed after {MAX_RETRIES} retries: {last_error}")

    def _call_json(
        self,
        user_message: str,
        system_prompt: Optional[str] = None,
        temperature: float = TEMPERATURE,
    ) -> dict:
        """Call Claude and parse response as JSON. Handles markdown code fences."""
        prompt = (
            user_message
            + "\n\nRespond ONLY with valid JSON. No markdown fences, no commentary."
        )
        raw = self._call(prompt, system_prompt=system_prompt, temperature=temperature)

        # Strip markdown code fences if present
        raw = raw.strip()
        if raw.startswith("```"):
            first_nl = raw.find("\n")
            if first_nl != -1:
                raw = raw[first_nl + 1 :]
            if raw.endswith("```"):
                raw = raw[:-3]
            raw = raw.strip()

        try:
            return json.loads(raw)
        except json.JSONDecodeError as e:
            raise AgentError(
                f"Agent '{self.role_name}' failed to produce valid JSON: {e}\nRaw:\n{raw[:500]}"
            )

    def run(self, context: "AgentContext") -> "AgentContext":
        """Execute this agent's task. Override in subclasses."""
        raise NotImplementedError
