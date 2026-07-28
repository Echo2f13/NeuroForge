"""Tests for the NeuroForge LLM client.

Tests the provider abstraction, fallback chain, JSON parsing,
and exponential backoff logic without making real API calls.
"""

import json
import time
from unittest.mock import MagicMock, patch

import pytest
from pydantic import BaseModel

from src.llm import (
    BACKOFF_BASE,
    BACKOFF_MULTIPLIER,
    DEFAULT_CONFIGS,
    FALLBACK_CHAIN,
    MAX_RETRIES,
    AllProvidersFailedError,
    JSONParsingError,
    LLMClient,
    LLMConfig,
    LLMError,
    LLMProvider,
    RateLimitError,
)


# ---------------------------------------------------------------------------
# Test models for structured output
# ---------------------------------------------------------------------------


class TopicList(BaseModel):
    topics: list[str]
    count: int


class SimpleFact(BaseModel):
    fact: str
    confidence: float


# ---------------------------------------------------------------------------
# Provider Enum & Config Tests
# ---------------------------------------------------------------------------


class TestLLMProvider:
    def test_provider_values(self):
        assert LLMProvider.GROQ == "groq"
        assert LLMProvider.OPENROUTER == "openrouter"
        assert LLMProvider.GITHUB == "github"

    def test_provider_count(self):
        assert len(LLMProvider) == 3


class TestLLMConfig:
    def test_default_config_structure(self):
        config = LLMConfig(
            provider=LLMProvider.GROQ,
            model="test-model",
            api_key_env="TEST_KEY",
        )
        assert config.temperature == 0.7
        assert config.max_tokens == 2048

    def test_custom_config(self):
        config = LLMConfig(
            provider=LLMProvider.OPENROUTER,
            model="custom-model",
            temperature=0.3,
            max_tokens=4096,
            api_key_env="CUSTOM_KEY",
        )
        assert config.temperature == 0.3
        assert config.max_tokens == 4096

    def test_default_configs_exist_for_all_providers(self):
        for provider in LLMProvider:
            assert provider in DEFAULT_CONFIGS
            config = DEFAULT_CONFIGS[provider]
            assert config.provider == provider
            assert config.model
            assert config.api_key_env


# ---------------------------------------------------------------------------
# Client Initialization Tests
# ---------------------------------------------------------------------------


class TestClientInit:
    @patch.dict(
        "os.environ",
        {
            "GROQ_API_KEY": "test-groq-key",
            "OPENROUTER_API_KEY": "test-or-key",
            "GITHUB_TOKEN": "test-gh-key",
        },
    )
    def test_all_providers_initialized(self):
        client = LLMClient()
        assert LLMProvider.GROQ in client.available_providers
        assert LLMProvider.OPENROUTER in client.available_providers
        assert LLMProvider.GITHUB in client.available_providers

    @patch.dict("os.environ", {"GROQ_API_KEY": "test-key"}, clear=True)
    def test_partial_providers(self):
        client = LLMClient()
        assert LLMProvider.GROQ in client.available_providers
        assert LLMProvider.OPENROUTER not in client.available_providers
        assert LLMProvider.GITHUB not in client.available_providers

    @patch.dict("os.environ", {}, clear=True)
    def test_no_providers_available(self):
        client = LLMClient()
        assert len(client.available_providers) == 0

    @patch.dict("os.environ", {"GROQ_API_KEY": "key1", "GITHUB_TOKEN": "key2"}, clear=True)
    def test_is_available(self):
        client = LLMClient()
        assert client.is_available(LLMProvider.GROQ) is True
        assert client.is_available(LLMProvider.OPENROUTER) is False
        assert client.is_available(LLMProvider.GITHUB) is True


# ---------------------------------------------------------------------------
# Fallback Chain Tests
# ---------------------------------------------------------------------------


class TestFallbackChain:
    def test_fallback_order(self):
        assert FALLBACK_CHAIN == [
            LLMProvider.GROQ,
            LLMProvider.OPENROUTER,
            LLMProvider.GITHUB,
        ]

    @patch.dict(
        "os.environ",
        {
            "GROQ_API_KEY": "key1",
            "OPENROUTER_API_KEY": "key2",
            "GITHUB_TOKEN": "key3",
        },
    )
    def test_preferred_provider_first(self):
        client = LLMClient()
        chain = client._get_available_providers(preferred=LLMProvider.GITHUB)
        assert chain[0] == LLMProvider.GITHUB

    @patch.dict(
        "os.environ",
        {"GROQ_API_KEY": "key1", "OPENROUTER_API_KEY": "key2"},
        clear=True,
    )
    def test_missing_preferred_falls_back(self):
        client = LLMClient()
        chain = client._get_available_providers(preferred=LLMProvider.GITHUB)
        # GITHUB not available, should return available providers in order
        assert LLMProvider.GITHUB not in chain
        assert chain[0] == LLMProvider.GROQ


# ---------------------------------------------------------------------------
# Generate Tests (with mocked API calls)
# ---------------------------------------------------------------------------


class TestGenerate:
    @patch.dict("os.environ", {"GROQ_API_KEY": "test-key"}, clear=True)
    def test_generate_success(self):
        client = LLMClient()

        # Mock the OpenAI client response
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Photosynthesis converts sunlight to energy."
        mock_response.usage.prompt_tokens = 10
        mock_response.usage.completion_tokens = 8
        mock_response.usage.total_tokens = 18

        client._clients[LLMProvider.GROQ].chat.completions.create = MagicMock(
            return_value=mock_response
        )

        text, usage = client.generate("Explain photosynthesis")
        assert text == "Photosynthesis converts sunlight to energy."
        assert usage["provider"] == "groq"
        assert usage["total_tokens"] == 18
        assert "latency_seconds" in usage

    @patch.dict("os.environ", {}, clear=True)
    def test_generate_no_providers(self):
        client = LLMClient()
        with pytest.raises(LLMError, match="No providers available"):
            client.generate("Hello")

    @patch.dict(
        "os.environ",
        {"GROQ_API_KEY": "key1", "OPENROUTER_API_KEY": "key2"},
        clear=True,
    )
    def test_generate_fallback_on_rate_limit(self):
        client = LLMClient()

        # Groq raises rate limit error
        client._clients[LLMProvider.GROQ].chat.completions.create = MagicMock(
            side_effect=Exception("Error code: 429 - Rate limit exceeded")
        )

        # OpenRouter succeeds
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Fallback response"
        mock_response.usage.prompt_tokens = 5
        mock_response.usage.completion_tokens = 3
        mock_response.usage.total_tokens = 8

        client._clients[LLMProvider.OPENROUTER].chat.completions.create = MagicMock(
            return_value=mock_response
        )

        # Patch time.sleep to avoid actual delays in tests
        with patch("src.llm.time.sleep"):
            text, usage = client.generate("Hello")

        assert text == "Fallback response"
        assert usage["provider"] == "openrouter"

    @patch.dict("os.environ", {"GROQ_API_KEY": "key1"}, clear=True)
    def test_all_providers_fail(self):
        client = LLMClient()

        client._clients[LLMProvider.GROQ].chat.completions.create = MagicMock(
            side_effect=Exception("Server error 500")
        )

        with pytest.raises(AllProvidersFailedError):
            client.generate("Hello")


# ---------------------------------------------------------------------------
# Exponential Backoff Tests
# ---------------------------------------------------------------------------


class TestBackoff:
    def test_backoff_constants(self):
        assert MAX_RETRIES == 3
        assert BACKOFF_BASE == 1.0
        assert BACKOFF_MULTIPLIER == 2.0

    def test_backoff_schedule(self):
        """Verify exponential backoff produces 1s, 2s, 4s."""
        expected = [1.0, 2.0, 4.0]
        for attempt in range(MAX_RETRIES):
            backoff = BACKOFF_BASE * (BACKOFF_MULTIPLIER ** attempt)
            assert backoff == expected[attempt]

    @patch.dict("os.environ", {"GROQ_API_KEY": "key1"}, clear=True)
    def test_backoff_called_on_retries(self):
        client = LLMClient()

        # Always rate limit
        client._clients[LLMProvider.GROQ].chat.completions.create = MagicMock(
            side_effect=Exception("429 rate limit")
        )

        sleep_calls = []
        with patch("src.llm.time.sleep", side_effect=lambda s: sleep_calls.append(s)):
            with pytest.raises(AllProvidersFailedError):
                client.generate("Hello")

        # Should have backed off 3 times (attempts 0, 1, 2)
        assert len(sleep_calls) == 3
        assert sleep_calls == [1.0, 2.0, 4.0]


# ---------------------------------------------------------------------------
# JSON Parsing Tests
# ---------------------------------------------------------------------------


class TestGenerateJSON:
    @patch.dict("os.environ", {"GROQ_API_KEY": "test-key"}, clear=True)
    def test_parse_clean_json(self):
        client = LLMClient()

        json_output = json.dumps({"topics": ["math", "physics"], "count": 2})
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = json_output
        mock_response.usage.prompt_tokens = 20
        mock_response.usage.completion_tokens = 15
        mock_response.usage.total_tokens = 35

        client._clients[LLMProvider.GROQ].chat.completions.create = MagicMock(
            return_value=mock_response
        )

        result, usage = client.generate_json(
            prompt="List topics", response_model=TopicList
        )
        assert isinstance(result, TopicList)
        assert result.topics == ["math", "physics"]
        assert result.count == 2

    @patch.dict("os.environ", {"GROQ_API_KEY": "test-key"}, clear=True)
    def test_parse_json_with_markdown_fences(self):
        client = LLMClient()

        json_output = '```json\n{"topics": ["bio"], "count": 1}\n```'
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = json_output
        mock_response.usage.prompt_tokens = 20
        mock_response.usage.completion_tokens = 15
        mock_response.usage.total_tokens = 35

        client._clients[LLMProvider.GROQ].chat.completions.create = MagicMock(
            return_value=mock_response
        )

        result, usage = client.generate_json(
            prompt="List topics", response_model=TopicList
        )
        assert isinstance(result, TopicList)
        assert result.topics == ["bio"]

    @patch.dict("os.environ", {"GROQ_API_KEY": "test-key"}, clear=True)
    def test_json_retry_on_invalid_output(self):
        client = LLMClient()

        # First call returns invalid JSON
        bad_response = MagicMock()
        bad_response.choices = [MagicMock()]
        bad_response.choices[0].message.content = "Here are the topics: math, science"
        bad_response.usage.prompt_tokens = 10
        bad_response.usage.completion_tokens = 10
        bad_response.usage.total_tokens = 20

        # Second call (retry) returns valid JSON
        good_response = MagicMock()
        good_response.choices = [MagicMock()]
        good_response.choices[0].message.content = json.dumps(
            {"topics": ["math", "science"], "count": 2}
        )
        good_response.usage.prompt_tokens = 30
        good_response.usage.completion_tokens = 15
        good_response.usage.total_tokens = 45

        client._clients[LLMProvider.GROQ].chat.completions.create = MagicMock(
            side_effect=[bad_response, good_response]
        )

        result, usage = client.generate_json(
            prompt="List topics", response_model=TopicList
        )
        assert isinstance(result, TopicList)
        assert result.topics == ["math", "science"]
        assert usage.get("retried") is True

    @patch.dict("os.environ", {"GROQ_API_KEY": "test-key"}, clear=True)
    def test_json_parse_failure_after_retry(self):
        client = LLMClient()

        # Both calls return invalid JSON
        bad_response = MagicMock()
        bad_response.choices = [MagicMock()]
        bad_response.choices[0].message.content = "Not JSON at all"
        bad_response.usage.prompt_tokens = 10
        bad_response.usage.completion_tokens = 5
        bad_response.usage.total_tokens = 15

        client._clients[LLMProvider.GROQ].chat.completions.create = MagicMock(
            return_value=bad_response
        )

        with pytest.raises(JSONParsingError):
            client.generate_json(prompt="List topics", response_model=TopicList)


# ---------------------------------------------------------------------------
# Internal Parsing Helper Tests
# ---------------------------------------------------------------------------


class TestTryParseJSON:
    @patch.dict("os.environ", {"GROQ_API_KEY": "test-key"}, clear=True)
    def test_valid_json(self):
        client = LLMClient()
        result = client._try_parse_json(
            '{"fact": "Water is H2O", "confidence": 0.95}', SimpleFact
        )
        assert result is not None
        assert result.fact == "Water is H2O"
        assert result.confidence == 0.95

    @patch.dict("os.environ", {"GROQ_API_KEY": "test-key"}, clear=True)
    def test_invalid_json(self):
        client = LLMClient()
        result = client._try_parse_json("not json", SimpleFact)
        assert result is None

    @patch.dict("os.environ", {"GROQ_API_KEY": "test-key"}, clear=True)
    def test_json_missing_required_fields(self):
        client = LLMClient()
        result = client._try_parse_json('{"fact": "test"}', SimpleFact)
        assert result is None  # Missing 'confidence' field

    @patch.dict("os.environ", {"GROQ_API_KEY": "test-key"}, clear=True)
    def test_strip_code_fences(self):
        client = LLMClient()
        raw = '```\n{"fact": "test", "confidence": 0.8}\n```'
        result = client._try_parse_json(raw, SimpleFact)
        assert result is not None
        assert result.fact == "test"


# ---------------------------------------------------------------------------
# Logging Tests
# ---------------------------------------------------------------------------


class TestLogging:
    @patch.dict("os.environ", {"GROQ_API_KEY": "test-key"}, clear=True)
    def test_successful_call_logs_info(self, caplog):
        client = LLMClient()

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Response"
        mock_response.usage.prompt_tokens = 5
        mock_response.usage.completion_tokens = 3
        mock_response.usage.total_tokens = 8

        client._clients[LLMProvider.GROQ].chat.completions.create = MagicMock(
            return_value=mock_response
        )

        with caplog.at_level("INFO", logger="neuroforge.llm"):
            client.generate("test")

        # Check that logging captured provider, model, tokens, latency
        assert any("groq" in record.message for record in caplog.records)
        assert any("tokens: 8" in record.message for record in caplog.records)
        assert any("latency:" in record.message for record in caplog.records)
