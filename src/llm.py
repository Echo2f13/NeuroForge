"""NeuroForge — Unified LLM Client.

Provides a single interface to two free-tier LLM providers:
- Groq (Llama 3.3 70B Versatile) — primary, fast
- OpenRouter (NVIDIA Nemotron 3 Super 120B free) — fallback

Note: GitHub Models was retired on July 30, 2026.

Features:
- Provider fallback chain on rate-limit (429) errors
- Exponential backoff (1s, 2s, 4s, 8s) with max 3 retries per provider
- Structured JSON output parsing with Pydantic validation + retry
- Logging of every call: provider, model, tokens, latency
"""

from __future__ import annotations

import json
import logging
import os
import time
from enum import Enum
from typing import Any, Optional, Type, TypeVar

from dotenv import load_dotenv
from openai import OpenAI
from pydantic import BaseModel, Field

# Load environment variables from .env file
load_dotenv()

logger = logging.getLogger("neuroforge.llm")

T = TypeVar("T", bound=BaseModel)


# ---------------------------------------------------------------------------
# Provider Enum & Config
# ---------------------------------------------------------------------------


class LLMProvider(str, Enum):
    """Supported LLM providers."""

    GROQ = "groq"
    OPENROUTER = "openrouter"


class LLMConfig(BaseModel):
    """Configuration for a single LLM provider."""

    provider: LLMProvider
    model: str
    temperature: float = 0.7
    max_tokens: int = 2048
    api_key_env: str  # Name of the environment variable holding the API key


# ---------------------------------------------------------------------------
# Default provider configurations
# ---------------------------------------------------------------------------

DEFAULT_CONFIGS: dict[LLMProvider, LLMConfig] = {
    LLMProvider.GROQ: LLMConfig(
        provider=LLMProvider.GROQ,
        model="llama-3.3-70b-versatile",
        temperature=0.7,
        max_tokens=2048,
        api_key_env="GROQ_API_KEY",
    ),
    LLMProvider.OPENROUTER: LLMConfig(
        provider=LLMProvider.OPENROUTER,
        model="nvidia/nemotron-3-super-120b-a12b:free",
        temperature=0.7,
        max_tokens=2048,
        api_key_env="OPENROUTER_API_KEY",
    ),
}

# Provider fallback order: Groq → OpenRouter
FALLBACK_CHAIN: list[LLMProvider] = [
    LLMProvider.GROQ,
    LLMProvider.OPENROUTER,
]

# Base URLs for each provider
PROVIDER_BASE_URLS: dict[LLMProvider, str] = {
    LLMProvider.GROQ: "https://api.groq.com/openai/v1",
    LLMProvider.OPENROUTER: "https://openrouter.ai/api/v1",
}

# Max retries per provider before falling back
MAX_RETRIES = 3

# Exponential backoff base (seconds): 1, 2, 4, 8
BACKOFF_BASE = 1.0
BACKOFF_MULTIPLIER = 2.0


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class LLMError(Exception):
    """Base exception for LLM client errors."""

    pass


class RateLimitError(LLMError):
    """Raised when a provider returns 429 (rate limit exceeded)."""

    def __init__(self, provider: LLMProvider, message: str = ""):
        self.provider = provider
        super().__init__(f"Rate limit hit on {provider.value}: {message}")


class AllProvidersFailedError(LLMError):
    """Raised when all providers in the fallback chain have failed."""

    def __init__(self, errors: list[str]):
        self.errors = errors
        super().__init__(
            f"All providers failed. Errors: {'; '.join(errors)}"
        )


class JSONParsingError(LLMError):
    """Raised when LLM output cannot be parsed as valid JSON."""

    def __init__(self, raw_output: str, message: str = ""):
        self.raw_output = raw_output
        super().__init__(f"JSON parsing failed: {message}")


# ---------------------------------------------------------------------------
# LLM Client
# ---------------------------------------------------------------------------


class LLMClient:
    """Unified LLM client with provider fallback and structured output support.

    Usage:
        client = LLMClient()
        response = client.generate("Explain photosynthesis in 3 sentences.")
        structured = client.generate_json(
            prompt="List 3 key topics",
            response_model=MyModel,
        )
    """

    def __init__(
        self,
        configs: Optional[dict[LLMProvider, LLMConfig]] = None,
    ):
        """Initialize the LLM client.

        Args:
            configs: Optional override for provider configurations.
                     Defaults to DEFAULT_CONFIGS.
        """
        self.configs = configs or DEFAULT_CONFIGS.copy()
        self._clients: dict[LLMProvider, OpenAI] = {}
        self._init_clients()

    def _init_clients(self) -> None:
        """Initialize OpenAI-compatible clients for each configured provider."""
        for provider, config in self.configs.items():
            api_key = os.environ.get(config.api_key_env)
            if not api_key:
                logger.warning(
                    f"API key env var '{config.api_key_env}' not set — "
                    f"{provider.value} will be unavailable."
                )
                continue

            self._clients[provider] = OpenAI(
                api_key=api_key,
                base_url=PROVIDER_BASE_URLS[provider],
            )
            logger.info(
                f"Initialized {provider.value} client "
                f"(model: {config.model})"
            )

    def _get_available_providers(
        self, preferred: Optional[LLMProvider] = None
    ) -> list[LLMProvider]:
        """Get ordered list of available providers starting from preferred.

        Args:
            preferred: If set, this provider will be tried first.

        Returns:
            List of providers that have valid API keys configured.
        """
        if preferred and preferred in self._clients:
            chain = [preferred] + [
                p for p in FALLBACK_CHAIN if p != preferred and p in self._clients
            ]
        else:
            chain = [p for p in FALLBACK_CHAIN if p in self._clients]
        return chain

    def _call_provider(
        self,
        provider: LLMProvider,
        messages: list[dict[str, str]],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> tuple[str, dict[str, Any]]:
        """Make a single call to a specific provider.

        Args:
            provider: The provider to call.
            messages: Chat messages in OpenAI format.
            temperature: Override temperature (uses config default if None).
            max_tokens: Override max_tokens (uses config default if None).

        Returns:
            Tuple of (response_text, usage_info).

        Raises:
            RateLimitError: If provider returns 429.
            LLMError: For other API errors.
        """
        config = self.configs[provider]
        client = self._clients[provider]
        temp = temperature if temperature is not None else config.temperature
        tokens = max_tokens if max_tokens is not None else config.max_tokens

        start_time = time.time()
        try:
            response = client.chat.completions.create(
                model=config.model,
                messages=messages,
                temperature=temp,
                max_tokens=tokens,
            )
        except Exception as e:
            latency = time.time() - start_time
            error_msg = str(e)

            # Detect rate limit errors (429)
            if "429" in error_msg or "rate" in error_msg.lower():
                logger.warning(
                    f"[{provider.value}] Rate limit hit after {latency:.2f}s"
                )
                raise RateLimitError(provider, error_msg)

            logger.error(
                f"[{provider.value}] API error after {latency:.2f}s: {error_msg}"
            )
            raise LLMError(f"{provider.value} error: {error_msg}")

        latency = time.time() - start_time

        # Extract response content and usage
        content = response.choices[0].message.content or ""
        usage_info = {
            "provider": provider.value,
            "model": config.model,
            "prompt_tokens": getattr(response.usage, "prompt_tokens", 0),
            "completion_tokens": getattr(response.usage, "completion_tokens", 0),
            "total_tokens": getattr(response.usage, "total_tokens", 0),
            "latency_seconds": round(latency, 3),
        }

        logger.info(
            f"[{provider.value}] {config.model} | "
            f"tokens: {usage_info['total_tokens']} | "
            f"latency: {usage_info['latency_seconds']}s"
        )

        return content, usage_info

    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        provider: Optional[LLMProvider] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> tuple[str, dict[str, Any]]:
        """Generate a text response with automatic fallback on rate limits.

        Args:
            prompt: The user prompt.
            system_prompt: Optional system prompt for context/instructions.
            provider: Preferred provider (falls back to chain if unavailable).
            temperature: Override temperature.
            max_tokens: Override max_tokens.

        Returns:
            Tuple of (response_text, usage_info dict).

        Raises:
            AllProvidersFailedError: If all providers in the chain fail.
        """
        messages: list[dict[str, str]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        chain = self._get_available_providers(preferred=provider)
        if not chain:
            raise LLMError(
                "No providers available. Check your API key environment variables."
            )

        errors: list[str] = []

        for current_provider in chain:
            for attempt in range(MAX_RETRIES):
                try:
                    return self._call_provider(
                        provider=current_provider,
                        messages=messages,
                        temperature=temperature,
                        max_tokens=max_tokens,
                    )
                except RateLimitError as e:
                    backoff = BACKOFF_BASE * (BACKOFF_MULTIPLIER ** attempt)
                    logger.warning(
                        f"[{current_provider.value}] Retry {attempt + 1}/{MAX_RETRIES} "
                        f"— backing off {backoff:.1f}s"
                    )
                    errors.append(
                        f"{current_provider.value} attempt {attempt + 1}: {e}"
                    )
                    time.sleep(backoff)
                except LLMError as e:
                    errors.append(f"{current_provider.value}: {e}")
                    break  # Non-rate-limit error → skip to next provider

            logger.warning(
                f"[{current_provider.value}] Exhausted retries, "
                f"falling back to next provider."
            )

        raise AllProvidersFailedError(errors)

    def generate_json(
        self,
        prompt: str,
        response_model: Type[T],
        system_prompt: Optional[str] = None,
        provider: Optional[LLMProvider] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> tuple[T, dict[str, Any]]:
        """Generate structured JSON output validated against a Pydantic model.

        If the LLM output isn't valid JSON or doesn't match the model,
        re-prompts once with error feedback.

        Args:
            prompt: The user prompt (should ask for JSON output).
            response_model: Pydantic model class to validate against.
            system_prompt: Optional system prompt. If None, a JSON-focused
                          system prompt is generated automatically.
            provider: Preferred provider.
            temperature: Override temperature.
            max_tokens: Override max_tokens.

        Returns:
            Tuple of (parsed Pydantic model instance, usage_info).

        Raises:
            JSONParsingError: If JSON parsing fails after retry.
            AllProvidersFailedError: If all providers fail.
        """
        # Build a JSON-focused system prompt
        schema_str = json.dumps(response_model.model_json_schema(), indent=2)
        json_system = system_prompt or ""
        json_system += (
            "\n\nYou MUST respond with valid JSON only. No markdown, no explanation."
            "\nYour response must conform to this JSON schema:\n"
            f"```json\n{schema_str}\n```"
        )

        # First attempt
        raw_text, usage = self.generate(
            prompt=prompt,
            system_prompt=json_system,
            provider=provider,
            temperature=temperature,
            max_tokens=max_tokens,
        )

        parsed = self._try_parse_json(raw_text, response_model)
        if parsed is not None:
            return parsed, usage

        # Retry: re-prompt with error feedback
        logger.warning("JSON parsing failed on first attempt — retrying with feedback.")
        retry_prompt = (
            f"Your previous response was not valid JSON or didn't match the schema.\n"
            f"Previous output:\n{raw_text[:1000]}\n\n"
            f"Please respond with ONLY valid JSON matching this schema:\n"
            f"```json\n{schema_str}\n```\n\n"
            f"Original request: {prompt}"
        )

        raw_text_retry, usage_retry = self.generate(
            prompt=retry_prompt,
            system_prompt=json_system,
            provider=provider,
            temperature=max(0.3, (temperature or 0.7) - 0.3),
            max_tokens=max_tokens,
        )

        # Merge usage info
        combined_usage = {
            **usage_retry,
            "total_tokens": usage.get("total_tokens", 0)
            + usage_retry.get("total_tokens", 0),
            "retried": True,
        }

        parsed = self._try_parse_json(raw_text_retry, response_model)
        if parsed is not None:
            return parsed, combined_usage

        raise JSONParsingError(
            raw_output=raw_text_retry,
            message=f"Failed to parse as {response_model.__name__} after retry.",
        )

    def _try_parse_json(
        self, raw_text: str, response_model: Type[T]
    ) -> Optional[T]:
        """Attempt to parse raw LLM text as JSON and validate with Pydantic.

        Handles common issues like markdown code fences around JSON.
        """
        text = raw_text.strip()

        # Strip markdown code fences if present
        if text.startswith("```"):
            lines = text.split("\n")
            # Remove first line (```json or ```) and last line (```)
            if lines[-1].strip() == "```":
                lines = lines[1:-1]
            else:
                lines = lines[1:]
            text = "\n".join(lines)

        try:
            data = json.loads(text)
            return response_model.model_validate(data)
        except (json.JSONDecodeError, Exception) as e:
            logger.debug(f"JSON parse error: {e}")
            return None

    @property
    def available_providers(self) -> list[LLMProvider]:
        """List of providers with valid API keys configured."""
        return list(self._clients.keys())

    def is_available(self, provider: LLMProvider) -> bool:
        """Check if a specific provider is available (API key set)."""
        return provider in self._clients
