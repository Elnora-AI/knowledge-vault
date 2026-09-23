"""Provider selection for LLM formatting: the user's key decides, OpenRouter or Anthropic."""

import pytest

pytest.importorskip("anthropic")

from connectors.framework import ConnectorConfig  # noqa: E402
from connectors.framework.formatter import _anthropic_client  # noqa: E402

_VARS = ("OPENROUTER_API_KEY", "ANTHROPIC_API_KEY", "ANTHROPIC_GATEWAY_URL", "ANTHROPIC_GATEWAY_KEY",
         "AZURE_ANTHROPIC_ENDPOINT", "AZURE_ANTHROPIC_API_KEY")


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    for var in _VARS:
        monkeypatch.delenv(var, raising=False)


def test_openrouter_key_routes_to_openrouter(monkeypatch, tmp_path):
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test")
    client = _anthropic_client(ConnectorConfig(vault_root=tmp_path))
    assert str(client.base_url).startswith("https://openrouter.ai/api")


def test_direct_anthropic_key_still_works(monkeypatch, tmp_path):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    client = _anthropic_client(ConnectorConfig(vault_root=tmp_path))
    assert str(client.base_url).startswith("https://api.anthropic.com")


def test_openrouter_wins_when_both_keys_are_set(monkeypatch, tmp_path):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test")
    client = _anthropic_client(ConnectorConfig(vault_root=tmp_path))
    assert str(client.base_url).startswith("https://openrouter.ai/api")


def test_no_key_means_no_client(tmp_path):
    assert _anthropic_client(ConnectorConfig(vault_root=tmp_path)) is None
