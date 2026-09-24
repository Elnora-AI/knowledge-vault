"""Which LLM provider formats records. Any key drives it.

The provider is picked in this order:

  1. ``llm_provider`` in the connector config, or ``LLM_PROVIDER`` in the
     environment, when set (anthropic | openai | google | openrouter | groq |
     deepseek | xai | mistral | custom)
  2. ``LLM_BASE_URL``, when set → custom: any OpenAI-compatible endpoint (Azure
     OpenAI, Together, Fireworks, LiteLLM, a self-hosted vLLM/Ollama, …) with
     ``LLM_API_KEY`` and ``llm_model``
  3. the first provider below whose API key is set

``llm_model`` overrides the provider's default model.
"""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Provider:
    keys: tuple[str, ...]  # env vars that may hold the key; the first one set wins
    model: str
    base_url: str = ""  # OpenAI-compatible endpoint; empty = the Anthropic SDK


PROVIDERS: dict[str, Provider] = {
    # An Anthropic gateway or Azure AI Services key pairs with its endpoint var
    # (_ENDPOINT_FOR) and keeps precedence over a direct key, as before.
    "anthropic": Provider(("ANTHROPIC_GATEWAY_KEY", "AZURE_ANTHROPIC_API_KEY", "ANTHROPIC_API_KEY"),
                          "claude-sonnet-5"),
    "openai": Provider(("OPENAI_API_KEY",), "gpt-5", "https://api.openai.com/v1"),
    "google": Provider(("GOOGLE_GENERATIVE_AI_API_KEY", "GEMINI_API_KEY"), "gemini-flash-latest",
                       "https://generativelanguage.googleapis.com/v1beta/openai"),
    "openrouter": Provider(("OPENROUTER_API_KEY",), "openrouter/auto", "https://openrouter.ai/api/v1"),
    "groq": Provider(("GROQ_API_KEY",), "openai/gpt-oss-120b", "https://api.groq.com/openai/v1"),
    "deepseek": Provider(("DEEPSEEK_API_KEY",), "deepseek-chat", "https://api.deepseek.com/v1"),
    "xai": Provider(("XAI_API_KEY",), "grok-4.7", "https://api.x.ai/v1"),
    "mistral": Provider(("MISTRAL_API_KEY",), "mistral-large-latest", "https://api.mistral.ai/v1"),
}

_ALIASES = {"gemini": "google", "grok": "xai", "openai-compatible": "custom"}
_ENDPOINT_FOR = {"ANTHROPIC_GATEWAY_KEY": "ANTHROPIC_GATEWAY_URL",
                 "AZURE_ANTHROPIC_API_KEY": "AZURE_ANTHROPIC_ENDPOINT"}


@dataclass
class ResolvedProvider:
    name: str
    model: str
    api_key: str = ""
    key_env: str = ""  # env var the key came from, for status output; never the value
    base_url: str = ""
    problem: str = ""  # why formatting can't run as configured; empty when it can

    def describe(self) -> str:
        return f"{self.name} / {self.model}" + (f" — {self.problem}" if self.problem else "")


def _env(name: str) -> str:
    return os.environ.get(name, "").strip()


def _strip_v1(endpoint: str) -> str:
    """Strip a trailing /v1 — the Anthropic SDK appends /v1/messages itself."""
    base = endpoint.rstrip("/")
    return base[:-3] if base.endswith("/v1") else base


def resolve_provider(llm_provider: str = "", llm_model: str = "") -> ResolvedProvider:
    requested = (llm_provider or _env("LLM_PROVIDER")).lower()
    name = _ALIASES.get(requested, requested)

    if name == "custom" or (not name and _env("LLM_BASE_URL")):
        base_url = _env("LLM_BASE_URL")
        missing = [v for v, ok in (("LLM_BASE_URL", base_url), ("llm_model", llm_model)) if not ok]
        return ResolvedProvider(
            "custom", llm_model, _env("LLM_API_KEY"), "LLM_API_KEY", base_url,
            problem=f"custom provider needs {' and '.join(missing)}" if missing else "",
        )

    if name and name not in PROVIDERS:
        return ResolvedProvider(
            name, llm_model,
            problem=f'unknown llm_provider "{name}"; use one of {", ".join([*PROVIDERS, "custom"])}',
        )

    detected = name or next((p for p, spec in PROVIDERS.items() if any(_env(k) for k in spec.keys)), "")
    if not detected:
        all_keys = ", ".join(k for spec in PROVIDERS.values() for k in spec.keys)
        return ResolvedProvider(
            "anthropic", llm_model or PROVIDERS["anthropic"].model, key_env="ANTHROPIC_API_KEY",
            problem=f"no LLM key set; set one of {all_keys}, or LLM_BASE_URL for an OpenAI-compatible endpoint",
        )

    spec = PROVIDERS[detected]
    key_env = next((k for k in spec.keys if _env(k)), spec.keys[-1])
    api_key = _env(key_env)
    base_url, problem = spec.base_url, "" if api_key else f"{key_env} not set"
    if endpoint_env := _ENDPOINT_FOR.get(key_env):
        base_url = _strip_v1(_env(endpoint_env))
        problem = problem or ("" if base_url else f"{key_env} is set but {endpoint_env} is not")
    return ResolvedProvider(detected, llm_model or spec.model, api_key, key_env, base_url, problem)
