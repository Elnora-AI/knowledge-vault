"""Provider selection for LLM formatting: any key drives it, llm_provider chooses among several."""

import io
import json
from urllib.parse import urlparse

import pytest

from connectors.framework import ConnectorConfig
from connectors.framework.formatter import _llm_client, _OpenAICompatibleClient
from connectors.framework.llm_provider import PROVIDERS, resolve_provider

_VARS = ("LLM_PROVIDER", "LLM_BASE_URL", "LLM_API_KEY", "ANTHROPIC_GATEWAY_URL", "ANTHROPIC_GATEWAY_KEY",
         "AZURE_ANTHROPIC_ENDPOINT", "AZURE_ANTHROPIC_API_KEY",
         *(k for spec in PROVIDERS.values() for k in spec.keys))


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    for var in _VARS:
        monkeypatch.delenv(var, raising=False)


# --- resolution -------------------------------------------------------------

@pytest.mark.parametrize("name", list(PROVIDERS))
def test_each_provider_is_picked_from_its_key(monkeypatch, name):
    key_env = PROVIDERS[name].keys[-1]
    monkeypatch.setenv(key_env, "test-key")
    p = resolve_provider()
    assert (p.name, p.model, p.key_env, p.problem) == (name, PROVIDERS[name].model, key_env, "")


def test_anthropic_wins_when_several_keys_are_set(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    assert resolve_provider().name == "anthropic"


def test_llm_provider_chooses_among_several_keys(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    assert resolve_provider(llm_provider="openrouter").name == "openrouter"
    monkeypatch.setenv("LLM_PROVIDER", "OpenRouter")
    assert resolve_provider().name == "openrouter"


def test_aliases(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "g")
    assert resolve_provider(llm_provider="gemini").name == "google"


def test_llm_model_overrides_the_provider_default(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test")
    assert resolve_provider(llm_model="anthropic/claude-sonnet-5").model == "anthropic/claude-sonnet-5"


def test_chosen_provider_without_its_key_is_a_problem(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    p = resolve_provider(llm_provider="openai")
    assert p.name == "openai" and p.problem == "OPENAI_API_KEY not set"


def test_unknown_provider_is_a_problem():
    p = resolve_provider(llm_provider="acme")
    assert "unknown llm_provider" in p.problem and "custom" in p.problem


def test_no_key_is_a_problem():
    p = resolve_provider()
    assert p.problem.startswith("no LLM key set") and "OPENAI_API_KEY" in p.problem


def test_custom_endpoint_from_base_url(monkeypatch):
    monkeypatch.setenv("LLM_BASE_URL", "https://api.together.xyz/v1")
    monkeypatch.setenv("LLM_API_KEY", "t")
    p = resolve_provider(llm_model="meta-llama/Llama-3-70b")
    assert (p.name, p.base_url, p.problem) == ("custom", "https://api.together.xyz/v1", "")
    assert resolve_provider().problem == "custom provider needs llm_model"


def test_anthropic_gateway_and_azure_keep_precedence_over_a_direct_key(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    monkeypatch.setenv("AZURE_ANTHROPIC_API_KEY", "az")
    assert resolve_provider().problem == "AZURE_ANTHROPIC_API_KEY is set but AZURE_ANTHROPIC_ENDPOINT is not"
    monkeypatch.setenv("AZURE_ANTHROPIC_ENDPOINT", "https://x.services.ai.azure.com/anthropic/v1")
    assert resolve_provider().base_url == "https://x.services.ai.azure.com/anthropic"
    monkeypatch.setenv("ANTHROPIC_GATEWAY_KEY", "gw")
    monkeypatch.setenv("ANTHROPIC_GATEWAY_URL", "https://gateway.example.com")
    assert resolve_provider().key_env == "ANTHROPIC_GATEWAY_KEY"


# --- clients ------------------------------------------------------------------

def test_anthropic_key_builds_the_sdk_client(monkeypatch, tmp_path):
    pytest.importorskip("anthropic")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    client = _llm_client(ConnectorConfig(vault_root=tmp_path))
    assert urlparse(str(client._client.base_url)).hostname == "api.anthropic.com"


def test_openrouter_key_builds_the_chat_completions_client(monkeypatch, tmp_path):
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test")
    client = _llm_client(ConnectorConfig(vault_root=tmp_path))
    assert isinstance(client, _OpenAICompatibleClient)
    assert client._url == "https://openrouter.ai/api/v1/chat/completions"
    assert client._model == "openrouter/auto"


def test_no_key_means_no_client(tmp_path):
    assert _llm_client(ConnectorConfig(vault_root=tmp_path)) is None


def _sse(*events):
    lines = [f"data: {json.dumps(e)}\n".encode() for e in events] + [b"data: [DONE]\n"]
    return io.BytesIO(b"".join(lines))


def test_chat_completions_stream_is_joined_and_reports_truncation(monkeypatch):
    sent = {}

    def fake_urlopen(request, timeout):
        sent["body"] = json.loads(request.data)
        sent["auth"] = request.get_header("Authorization")
        return _sse(
            {"choices": [{"delta": {"role": "assistant", "content": ""}}]},
            {"choices": [{"delta": {"content": "Hello "}}]},
            {"choices": [{"delta": {"content": "world"}, "finish_reason": "length"}]},
        )

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    client = _OpenAICompatibleClient(resolve_provider())
    text, truncated = client.complete("sys", "user", max_tokens=16)
    assert (text, truncated) == ("Hello world", True)
    assert sent["auth"] == "Bearer sk-test"
    assert sent["body"]["max_completion_tokens"] == 16 and "max_tokens" not in sent["body"]
    assert sent["body"]["messages"][0] == {"role": "system", "content": "sys"}
    assert sent["body"]["stream"] is True

    monkeypatch.setenv("GROQ_API_KEY", "gq")
    _OpenAICompatibleClient(resolve_provider(llm_provider="groq")).complete("s", "u", max_tokens=8)
    assert sent["body"]["max_tokens"] == 8


def test_anthropic_sdk_stream_is_joined_and_reports_truncation(monkeypatch, tmp_path):
    pytest.importorskip("anthropic")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    client = _llm_client(ConnectorConfig(vault_root=tmp_path))
    sent = {}

    class Block:
        def __init__(self, type, text=""):
            self.type, self.text = type, text

    class Stream:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def get_final_message(self):
            return type("M", (), {"content": [Block("thinking"), Block("text", " Hello "), Block("text", "world")],
                                  "stop_reason": "max_tokens"})()

    class Messages:
        def stream(self, **kwargs):
            sent.update(kwargs)
            return Stream()

    client._client.messages = Messages()
    assert client.complete("sys", "user", max_tokens=16) == ("Hello world", True)
    assert sent["model"] == "claude-sonnet-5" and sent["max_tokens"] == 16
    assert sent["system"][0]["cache_control"] == {"type": "ephemeral"}
