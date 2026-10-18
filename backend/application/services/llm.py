from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx
from app.core.logging.logger import get_logger

from config.settings import get_settings

logger = get_logger(__name__)

# Preferred order when multiple keys are configured.
FALLBACK_ORDER = ("groq", "nvidia", "gemini", "openai", "anthropic")


@dataclass(slots=True)
class LLMResult:
    content: str
    provider: str
    model: str


class LLMError(RuntimeError):
    """Raised when no configured provider succeeds."""


async def chat_completion(
    *,
    system: str,
    user: str,
    temperature: float = 0.4,
    json_mode: bool = False,
    timeout: float = 45.0,
) -> LLMResult:
    """Try providers in FALLBACK_ORDER; skip those without an API key."""
    settings = get_settings()
    errors: list[str] = []

    for name in FALLBACK_ORDER:
        config = _provider_config(settings, name)
        if not config:
            continue
        try:
            content = await _call_provider(
                name=name,
                api_key=config["api_key"],
                model=config["model"],
                base_url=config.get("base_url"),
                system=system,
                user=user,
                temperature=temperature,
                json_mode=json_mode,
                timeout=timeout,
            )
            if content and content.strip():
                logger.info("LLM success via %s (%s)", name, config["model"])
                return LLMResult(
                    content=content.strip(), provider=name, model=config["model"]
                )
            errors.append(f"{name}: empty_response")
        except (
            httpx.HTTPError,
            TimeoutError,
            ValueError,
            RuntimeError,
            OSError,
        ) as exc:
            logger.warning("LLM provider %s failed: %s", name, exc)
            errors.append(f"{name}: {exc}")

    raise LLMError(
        "All LLM providers failed or unconfigured: "
        + "; ".join(errors or ["none configured"])
    )


def any_llm_configured() -> bool:
    settings = get_settings()
    return any(_provider_config(settings, name) for name in FALLBACK_ORDER)


def configured_providers() -> list[str]:
    settings = get_settings()
    return [name for name in FALLBACK_ORDER if _provider_config(settings, name)]


def _provider_config(settings: Any, name: str) -> dict[str, str] | None:
    if name == "groq":
        key = settings.groq_api_key
        if not key:
            return None
        return {
            "api_key": key,
            "model": settings.groq_model,
            "base_url": "https://api.groq.com/openai/v1",
        }
    if name == "nvidia":
        key = settings.nvidia_api_key
        if not key:
            return None
        return {
            "api_key": key,
            "model": settings.nvidia_model,
            "base_url": "https://integrate.api.nvidia.com/v1",
        }
    if name == "gemini":
        key = settings.gemini_api_key
        if not key:
            return None
        return {
            "api_key": key,
            "model": settings.gemini_model,
            "base_url": "https://generativelanguage.googleapis.com/v1beta/openai",
        }
    if name == "openai":
        key = settings.openai_api_key
        if not key:
            return None
        return {
            "api_key": key,
            "model": settings.openai_model,
            "base_url": "https://api.openai.com/v1",
        }
    if name == "anthropic":
        key = settings.anthropic_api_key
        if not key:
            return None
        return {
            "api_key": key,
            "model": settings.anthropic_model,
        }
    return None


async def _call_provider(
    *,
    name: str,
    api_key: str,
    model: str,
    base_url: str | None,
    system: str,
    user: str,
    temperature: float,
    json_mode: bool,
    timeout: float,
) -> str:
    if name == "anthropic":
        return await _call_anthropic(
            api_key=api_key,
            model=model,
            system=system,
            user=user,
            temperature=temperature,
            json_mode=json_mode,
            timeout=timeout,
        )
    assert base_url is not None
    return await _call_openai_compatible(
        base_url=base_url,
        api_key=api_key,
        model=model,
        system=system,
        user=user,
        temperature=temperature,
        json_mode=json_mode,
        timeout=timeout,
    )


async def _call_openai_compatible(
    *,
    base_url: str,
    api_key: str,
    model: str,
    system: str,
    user: str,
    temperature: float,
    json_mode: bool,
    timeout: float,
) -> str:
    payload: dict[str, Any] = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": temperature,
    }
    if json_mode:
        payload["response_format"] = {"type": "json_object"}
        payload["messages"][0]["content"] = (
            system + " Respond with a single JSON object only."
        )

    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.post(
            f"{base_url.rstrip('/')}/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
        )
        # Some OpenAI-compatible APIs reject response_format; retry without it.
        if response.status_code >= 400 and json_mode:
            payload.pop("response_format", None)
            response = await client.post(
                f"{base_url.rstrip('/')}/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
        response.raise_for_status()
        data = response.json()
    return str(data["choices"][0]["message"]["content"] or "")


async def _call_anthropic(
    *,
    api_key: str,
    model: str,
    system: str,
    user: str,
    temperature: float,
    json_mode: bool,
    timeout: float,
) -> str:
    system_text = system
    if json_mode:
        system_text += " Respond with a single JSON object only."
    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "max_tokens": 2048,
                "temperature": temperature,
                "system": system_text,
                "messages": [{"role": "user", "content": user}],
            },
        )
        response.raise_for_status()
        data = response.json()
    parts = data.get("content") or []
    texts = [str(part.get("text") or "") for part in parts if isinstance(part, dict)]
    return "".join(texts)
