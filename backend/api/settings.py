"""Settings API: model configuration and service status."""

import asyncio
import json
from pathlib import Path
from urllib.request import urlopen

from fastapi import APIRouter

from config.settings import get_settings
from core.config_store import ConfigStore
from schemas.settings import ModelsUpdateRequest

router = APIRouter(prefix="/api/settings", tags=["settings"])


def local_config_path() -> Path:
    """Path of config.local.yaml (project root). Overridable in tests."""
    return Path(__file__).resolve().parent.parent.parent / "config.local.yaml"


def _mask_key(api_key: str | None) -> str | None:
    if not api_key:
        return api_key
    return f"{api_key[:4]}***"


def _is_masked(api_key: str | None) -> bool:
    return bool(api_key) and api_key.endswith("***")


def _configured(config) -> str:
    """Configuration completeness for a model service. All providers need a
    model; cloud/openai additionally need an api_key, while local/ollama need
    an endpoint instead (they require no key)."""
    if not config.model:
        return "not_configured"
    if config.provider in ("cloud", "openai"):
        return "configured" if config.api_key else "not_configured"
    return "configured" if config.endpoint else "not_configured"


@router.get("/models")
async def get_model_settings() -> dict:
    """Return model configs with masked API keys."""
    models = get_settings().models
    return {
        name: {
            "provider": config.provider,
            "endpoint": config.endpoint,
            "api_key": _mask_key(config.api_key),
            "model": config.model,
        }
        for name, config in (
            ("chat", models.chat),
            ("embedding", models.embedding),
            ("asr", models.asr),
        )
    }


@router.put("/models")
async def update_model_settings(payload: ModelsUpdateRequest) -> dict:
    """Persist partial model config updates to config.local.yaml."""
    update: dict = {}
    for name in ("chat", "embedding", "asr"):
        section = getattr(payload, name)
        if section is None:
            continue
        fields = section.model_dump()
        # Masked keys round-tripped from the UI mean "keep current".
        if _is_masked(fields.get("api_key")):
            fields["api_key"] = None
        update[name] = fields
    if update:
        ConfigStore(local_config_path()).update_models(update)
    return await get_model_settings()


def _check_asr_health(endpoint: str) -> str:
    try:
        with urlopen(f"{endpoint.rstrip('/')}/health", timeout=3) as response:
            body = json.loads(response.read().decode("utf-8"))
        return "ok" if body.get("status") == "ok" else "unreachable"
    except (OSError, ValueError):
        # OSError: connection failed. ValueError: non-JSON body (JSONDecodeError).
        return "unreachable"


def _check_ollama_health(endpoint: str) -> str:
    try:
        with urlopen(f"{endpoint.rstrip('/')}/api/tags", timeout=3) as response:
            response.read()
        return "ok"
    except OSError:
        return "unreachable"


@router.get("/status")
async def get_service_status() -> dict:
    """Report per-service status without spending tokens."""
    models = get_settings().models
    asr_endpoint = models.asr.endpoint or "http://localhost:8001"

    async def model_status(config) -> dict:
        if config.provider == "ollama":
            endpoint = config.endpoint or "http://localhost:11434"
            health = await asyncio.to_thread(_check_ollama_health, endpoint)
            return {"status": health, "endpoint": endpoint}
        return {"status": _configured(config)}

    asr_status = await asyncio.to_thread(_check_asr_health, asr_endpoint)
    return {
        "chat": await model_status(models.chat),
        "embedding": await model_status(models.embedding),
        "asr": {"status": asr_status, "endpoint": asr_endpoint},
    }
