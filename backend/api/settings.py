"""Settings API: model configuration and service status."""

import asyncio
import json
from pathlib import Path
from typing import Literal
from urllib.parse import urlparse
from urllib.request import urlopen

from fastapi import APIRouter, HTTPException

from config.settings import get_settings, resolve_project_root
from core.config_store import ConfigStore
from schemas.settings import (
    ModelsUpdateRequest,
    PresetCreateRequest,
    PresetResponse,
    PresetUpdateRequest,
)
from storage.sqlite_client import SQLiteClient

router = APIRouter(prefix="/api/settings", tags=["settings"])


def db_path() -> Path:
    """Path of memento.db (data directory). Overridable in tests."""
    settings = get_settings()
    return settings.storage.data_dir / "memento.db"


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
            "protocol": config.protocol,
        }
        for name, config in (
            ("chat", models.chat),
            ("embedding", models.embedding),
            ("asr", models.asr),
        )
    }


@router.put("/models")
async def update_model_settings(payload: ModelsUpdateRequest) -> dict:
    """Persist partial model config updates to database."""
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
        ConfigStore(db_path()).update_models(update)
    return await get_model_settings()


def _check_asr_health(endpoint: str) -> str:
    health_base = endpoint.rstrip("/")
    parsed = urlparse(health_base)
    if parsed.path.rstrip("/") == "/v1":
        health_base = health_base[: -len(parsed.path.rstrip("/"))].rstrip("/")
    try:
        with urlopen(f"{health_base}/health", timeout=3) as response:
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
    except (OSError, ValueError):
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


@router.get("/models/{name}/api_key")
async def get_model_api_key(name: Literal["chat", "embedding", "asr"]) -> dict:
    """Return the plaintext api_key for a single model service.

    ``name`` must be one of ``chat``, ``embedding``, or ``asr``.
    Returns a 422 via FastAPI's path-validation if the name doesn't match
    the enum -- no custom error handling needed.
    """
    models = get_settings().models
    config = getattr(models, name)
    return {"api_key": config.api_key}


# ===== Preset Management =====


def _get_sqlite_client() -> SQLiteClient:
    """Get SQLiteClient instance for preset operations."""
    return SQLiteClient(db_path())


async def _generate_preset_name(model_name: str, sqlite: SQLiteClient) -> str:
    """Generate auto-incremented preset name like '预设1', '预设2', etc."""
    presets = await sqlite.list_presets(model_name)
    max_n = 0
    for preset in presets:
        if preset["name"].startswith("预设"):
            try:
                n = int(preset["name"][2:])
                max_n = max(max_n, n)
            except ValueError:
                pass
    return f"预设{max_n + 1}"


@router.get("/models/{model_name}/presets")
async def list_presets(
    model_name: Literal["chat", "embedding", "asr"]
) -> list[PresetResponse]:
    """List all presets for a model, with masked API keys."""
    sqlite = _get_sqlite_client()
    await sqlite.connect()
    try:
        presets = await sqlite.list_presets(model_name)
        # Mask API keys in config
        for preset in presets:
            config = json.loads(preset["config"]) if isinstance(preset["config"], str) else preset["config"]
            if "api_key" in config:
                config["api_key"] = _mask_key(config["api_key"])
            preset["config"] = config
        return presets
    finally:
        await sqlite.close()


@router.post("/models/{model_name}/presets", status_code=201)
async def create_preset(
    model_name: Literal["chat", "embedding", "asr"], payload: PresetCreateRequest
) -> PresetResponse:
    """Create a new preset for a model."""
    sqlite = _get_sqlite_client()
    await sqlite.connect()
    try:
        # Generate name if not provided
        name = payload.name
        if not name:
            name = await _generate_preset_name(model_name, sqlite)

        # Use the provided config directly
        config = payload.config.model_dump(exclude_none=True)

        # Create preset
        preset = await sqlite.create_preset(
            name=name, model_name=model_name, config=config
        )

        # Mask API key in response
        preset_config = json.loads(preset["config"]) if isinstance(preset["config"], str) else preset["config"]
        if "api_key" in preset_config:
            preset_config["api_key"] = _mask_key(preset_config["api_key"])
        preset["config"] = preset_config

        return preset
    finally:
        await sqlite.close()


@router.get("/models/{model_name}/presets/{preset_id}")
async def get_preset(
    model_name: Literal["chat", "embedding", "asr"], preset_id: str
) -> PresetResponse:
    """Get a specific preset by ID."""
    sqlite = _get_sqlite_client()
    await sqlite.connect()
    try:
        preset = await sqlite.get_preset(preset_id)
        if not preset or preset["model_name"] != model_name:
            raise HTTPException(status_code=404, detail="Preset not found")

        # Mask API key
        config = json.loads(preset["config"]) if isinstance(preset["config"], str) else preset["config"]
        if "api_key" in config:
            config["api_key"] = _mask_key(config["api_key"])
        preset["config"] = config

        return preset
    finally:
        await sqlite.close()


@router.patch("/models/{model_name}/presets/{preset_id}")
async def update_preset(
    model_name: Literal["chat", "embedding", "asr"],
    preset_id: str,
    payload: PresetUpdateRequest,
) -> PresetResponse:
    """Update a preset. Masked API keys are preserved."""
    sqlite = _get_sqlite_client()
    await sqlite.connect()
    try:
        # Get current preset
        current = await sqlite.get_preset(preset_id)
        if not current or current["model_name"] != model_name:
            raise HTTPException(status_code=404, detail="Preset not found")

        # Parse current config
        current_config = json.loads(current["config"]) if isinstance(current["config"], str) else current["config"]

        # Merge updates
        new_name = payload.name if payload.name is not None else current["name"]
        new_model_name = (
            payload.model_name if payload.model_name is not None else current["model_name"]
        )

        new_config = current_config.copy()
        if payload.config is not None:
            update_dict = payload.config.model_dump(exclude_none=True)
            # If API key is masked, keep current value
            if "api_key" in update_dict and _is_masked(update_dict["api_key"]):
                update_dict["api_key"] = current_config.get("api_key")
            new_config.update(update_dict)

        # Update preset
        updated = await sqlite.update_preset(
            preset_id=preset_id,
            name=new_name,
            model_name=new_model_name,
            config=new_config,
        )

        if not updated:
            raise HTTPException(status_code=404, detail="Preset not found")

        # Mask API key in response
        response_config = json.loads(updated["config"]) if isinstance(updated["config"], str) else updated["config"]
        if "api_key" in response_config:
            response_config["api_key"] = _mask_key(response_config["api_key"])
        updated["config"] = response_config

        return updated
    finally:
        await sqlite.close()


@router.delete("/models/{model_name}/presets/{preset_id}", status_code=204)
async def delete_preset(
    model_name: Literal["chat", "embedding", "asr"], preset_id: str
) -> None:
    """Delete a preset. If it was active, fallback to the first remaining preset."""
    sqlite = _get_sqlite_client()
    await sqlite.connect()
    try:
        # Check if this is the last preset
        presets = await sqlite.list_presets(model_name)
        if len(presets) == 1:
            raise HTTPException(400, "Cannot delete the last preset")

        # Check if preset exists and belongs to this model
        preset = await sqlite.get_preset(preset_id)
        if not preset or preset["model_name"] != model_name:
            raise HTTPException(status_code=404, detail="Preset not found")

        # Check if this was the active preset
        active = await sqlite.get_active_preset(model_name)
        was_active = active and active["preset_id"] == preset_id

        # Delete the preset
        deleted = await sqlite.delete_preset(preset_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Preset not found")

        # If it was active, fallback to first remaining preset
        if was_active:
            remaining = await sqlite.list_presets(model_name)
            if remaining:
                await sqlite.set_active_preset(model_name, remaining[0]["id"])
            else:
                await sqlite.clear_active_preset(model_name)
    finally:
        await sqlite.close()


@router.get("/models/{model_name}/active")
async def get_active_preset(
    model_name: Literal["chat", "embedding", "asr"]
) -> dict:
    """Get the currently active preset for a model."""
    sqlite = _get_sqlite_client()
    await sqlite.connect()
    try:
        active = await sqlite.get_active_preset(model_name)
        if not active or not active["preset_id"]:
            return {"preset_id": None}

        preset = await sqlite.get_preset(active["preset_id"])
        if not preset:
            return {"preset_id": None}

        # Mask API key
        config = json.loads(preset["config"]) if isinstance(preset["config"], str) else preset["config"]
        if "api_key" in config:
            config["api_key"] = _mask_key(config["api_key"])
        preset["config"] = config

        return {"preset_id": active["preset_id"], "preset": preset}
    finally:
        await sqlite.close()


@router.put("/models/{model_name}/active")
async def set_active_preset(
    model_name: Literal["chat", "embedding", "asr"], payload: dict
) -> dict:
    """Set the active preset for a model."""
    preset_id = payload.get("preset_id")
    if not preset_id:
        raise HTTPException(status_code=400, detail="preset_id is required")

    sqlite = _get_sqlite_client()
    await sqlite.connect()
    try:
        # Verify preset exists and belongs to this model
        preset = await sqlite.get_preset(preset_id)
        if not preset or preset["model_name"] != model_name:
            raise HTTPException(status_code=404, detail="Preset not found")

        # Set as active
        await sqlite.set_active_preset(model_name, preset_id)

        return {"preset_id": preset_id}
    finally:
        await sqlite.close()
