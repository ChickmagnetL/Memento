"""Settings API: model configuration and service status."""

import asyncio
import json
import sqlite3
from pathlib import Path
from typing import Any, Literal
from urllib.error import HTTPError
from urllib.parse import urlparse
from urllib.request import Request as UrlRequest, urlopen

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from config import settings as settings_module
from config.settings import (
    ModelConfig,
    Settings,
    _is_local_endpoint,
    _is_ollama_endpoint,
    get_settings,
)
from core.config_store import ConfigStore
from core.models.factory import build_embedding_client
from core.rag.embedding import EmbeddingError
from schemas.settings import (
    PresetConfig,
    ModelListRequest,
    ModelsUpdateRequest,
    PresetCreateRequest,
    PresetResponse,
    PresetUpdateRequest,
)
from storage.sqlite_client import SQLiteClient

router = APIRouter(prefix="/api/settings", tags=["settings"])


class EmbeddingSwitchRequest(BaseModel):
    confirm_reindex: bool = False


class EmbeddingSwitchPreviewConfigRequest(BaseModel):
    config: PresetConfig


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
    """Configuration completeness for a model service. Every service needs a
    model; a non-local (cloud/LAN) endpoint additionally needs an api_key.
    Local loopback endpoints (Ollama, a local ASR/embedding server) require
    no key."""
    if not config.model:
        return "not_configured"
    if _is_local_endpoint(config.endpoint):
        return "configured"
    return "configured" if config.api_key else "not_configured"


@router.get("/models")
async def get_model_settings() -> dict:
    """Return model configs with masked API keys."""
    models = get_settings().models
    return {
        name: {
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


MODEL_LIST_TIMEOUT_SECONDS = 10


def _read_json_url(url: str, headers: dict[str, str] | None = None) -> Any:
    request = UrlRequest(url, headers=headers or {})
    try:
        with urlopen(request, timeout=MODEL_LIST_TIMEOUT_SECONDS) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")[:200]
        raise HTTPException(
            status_code=502,
            detail=f"HTTP {exc.code}: {body}",
        ) from exc
    except OSError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except (ValueError, TypeError) as exc:
        raise HTTPException(status_code=502, detail="Malformed models response") from exc


def _parse_model_list_endpoint(endpoint: str):
    try:
        parsed = urlparse(endpoint)
        parsed.port
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Endpoint is invalid") from exc
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise HTTPException(status_code=400, detail="Endpoint is invalid")
    return parsed


def _is_ollama_model_list_config(config: dict[str, Any]) -> bool:
    return _is_ollama_endpoint(str(config.get("endpoint") or ""))


def _ollama_tags_base(endpoint: str) -> str:
    base = endpoint.rstrip("/")
    parsed = _parse_model_list_endpoint(base)
    if parsed.path.rstrip("/") == "/v1":
        base = base[: -len(parsed.path.rstrip("/"))].rstrip("/")
    return base


def _model_list_requires_api_key(config: dict[str, Any]) -> bool:
    # Cloud/LAN endpoints need a key; loopback endpoints (Ollama or any local
    # service) do not.
    return not _is_local_endpoint(config.get("endpoint"))


def _list_openai_compatible_models(config: dict[str, Any]) -> list[str]:
    endpoint = (config.get("endpoint") or "").rstrip("/")
    api_key = config.get("api_key")
    if not endpoint:
        raise HTTPException(status_code=400, detail="Endpoint is required to fetch models")
    _parse_model_list_endpoint(endpoint)
    if _model_list_requires_api_key(config) and not api_key:
        raise HTTPException(
            status_code=400,
            detail="API key is required to fetch models",
        )

    headers = {}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    response = _read_json_url(
        f"{endpoint}/models",
        headers,
    )
    data = response.get("data") if isinstance(response, dict) else None
    if not isinstance(data, list):
        raise HTTPException(status_code=502, detail="Malformed models response")
    return [
        item["id"]
        for item in data
        if isinstance(item, dict) and isinstance(item.get("id"), str)
    ]


def _list_ollama_models(config: dict[str, Any]) -> list[str]:
    endpoint = config.get("endpoint")
    if not endpoint:
        raise HTTPException(status_code=400, detail="Endpoint is required to fetch models")

    response = _read_json_url(f"{_ollama_tags_base(str(endpoint))}/api/tags")
    models = response.get("models") if isinstance(response, dict) else None
    if not isinstance(models, list):
        raise HTTPException(status_code=502, detail="Malformed Ollama models response")
    return [
        item["name"]
        for item in models
        if isinstance(item, dict) and isinstance(item.get("name"), str)
    ]


@router.get("/status")
async def get_service_status() -> dict:
    """Report per-service status without spending tokens."""
    models = get_settings().models
    asr_endpoint = models.asr.endpoint or "http://localhost:8001"

    async def model_status(config) -> dict:
        # Only a local Ollama endpoint is meaningfully probed (/api/tags);
        # arbitrary cloud endpoints aren't, so fall back to config completeness.
        if _is_ollama_endpoint(config.endpoint):
            health = await asyncio.to_thread(_check_ollama_health, config.endpoint)
            return {"status": health, "endpoint": config.endpoint}
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


def _get_embedding_reindex_manager(request: Request):
    manager = getattr(request.app.state, "embedding_reindex_jobs", None)
    if manager is None:
        raise HTTPException(
            status_code=503,
            detail="Embedding reindex manager is not initialized",
        )
    return manager


def _build_embedding_client_for_config(config: ModelConfig):
    settings = get_settings()
    models = settings.models.model_copy(update={"embedding": config})
    return build_embedding_client(settings.model_copy(update={"models": models}))


def _set_active_embedding_preset_sync(preset_id: str) -> None:
    conn = sqlite3.connect(db_path())
    try:
        conn.execute(
            """
            INSERT INTO active_preset (model_name, preset_id)
            VALUES ('embedding', ?)
            ON CONFLICT(model_name) DO UPDATE SET
                preset_id = excluded.preset_id,
                updated_at = CURRENT_TIMESTAMP
            """,
            (preset_id,),
        )
        conn.commit()
    finally:
        conn.close()


async def _load_preset_config(
    sqlite: SQLiteClient,
    *,
    model_name: Literal["chat", "embedding", "asr"],
    preset_id: str,
) -> dict[str, Any]:
    preset = await sqlite.get_preset(preset_id)
    if not preset or preset["model_name"] != model_name:
        raise HTTPException(status_code=404, detail="Preset not found")
    config = (
        json.loads(preset["config"])
        if isinstance(preset["config"], str)
        else preset["config"]
    )
    return config


def _resolve_embedding_config(raw_config: dict[str, Any]) -> ModelConfig:
    backend_dir = settings_module.resolve_backend_dir()
    project_root = settings_module.resolve_project_root(backend_dir)

    default_config_path = backend_dir / "config" / "default.yaml"
    user_config_path = project_root / "config.yaml"
    local_config_path = project_root / "config.local.yaml"

    config_data = settings_module._load_yaml_data(default_config_path)
    config_data = settings_module._merge_dicts(
        config_data,
        settings_module._load_yaml_data(user_config_path),
    )
    config_data = settings_module._merge_dicts(
        config_data,
        settings_module._load_yaml_data(local_config_path),
    )

    data_dir = config_data.get("storage", {}).get("data_dir", "~/memento_data")
    data_dir_path = Path(data_dir).expanduser()
    if not data_dir_path.is_absolute():
        data_dir_path = project_root / data_dir_path

    db_config = settings_module._load_db_config(data_dir_path / "memento.db")
    db_models = dict(db_config.get("models") or {})
    db_models.pop("embedding", None)
    if db_models:
        db_config = {**db_config, "models": db_models}
    else:
        db_config = {key: value for key, value in db_config.items() if key != "models"}

    config_data = settings_module._merge_dicts(config_data, db_config)
    config_data = settings_module._merge_dicts(
        config_data,
        {"models": {"embedding": raw_config}},
    )

    data_dir = config_data.get("storage", {}).get("data_dir", "~/memento_data")
    data_dir_path = Path(data_dir).expanduser()
    if not data_dir_path.is_absolute():
        data_dir_path = project_root / data_dir_path
    config_data.setdefault("storage", {})["data_dir"] = str(data_dir_path)

    return Settings(**config_data).models.embedding


def _merge_preset_config(
    current_config: dict[str, Any],
    update_config: PresetConfig | None,
) -> dict[str, Any]:
    new_config = current_config.copy()
    if update_config is not None:
        update_dict = update_config.model_dump(exclude_none=True)
        if "api_key" in update_dict and _is_masked(update_dict["api_key"]):
            update_dict["api_key"] = current_config.get("api_key")
        new_config.update(update_dict)
    return new_config


def _raise_if_embedding_reindex_running(request: Request) -> None:
    manager = _get_embedding_reindex_manager(request)
    active_job = getattr(manager, "active_job", None)
    if callable(active_job) and active_job() is not None:
        raise HTTPException(
            status_code=409,
            detail="Embedding index rebuild is already running",
        )


async def _preview_embedding_switch(
    request: Request, *, preset_id: str, config: ModelConfig
) -> dict:
    manager = _get_embedding_reindex_manager(request)
    try:
        embedding_client = _build_embedding_client_for_config(config)
        return await manager.preview_switch(
            preset_id=preset_id,
            embedding_client=embedding_client,
        )
    except EmbeddingError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


async def _generate_preset_name(model_name: str, sqlite: SQLiteClient) -> str:
    """Generate auto-incremented preset name like 'Preset 1', 'Preset 2', etc."""
    presets = await sqlite.list_presets(model_name)
    max_n = 0
    for preset in presets:
        # Match both the current English "Preset N" and the legacy Chinese "预设N"
        # so existing databases keep incrementing correctly after the rename.
        name = preset["name"]
        num_str = ""
        if name.startswith("Preset "):
            num_str = name[len("Preset "):]
        elif name.startswith("预设"):
            num_str = name[len("预设"):]
        if num_str:
            try:
                n = int(num_str)
                max_n = max(max_n, n)
            except ValueError:
                pass
    return f"Preset {max_n + 1}"


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


@router.get("/models/{model_name}/presets/{preset_id}/api_key")
async def get_preset_api_key(
    model_name: Literal["chat", "embedding", "asr"], preset_id: str
) -> dict:
    """Return the plaintext api_key for a specific preset."""
    sqlite = _get_sqlite_client()
    await sqlite.connect()
    try:
        preset = await sqlite.get_preset(preset_id)
        if not preset or preset["model_name"] != model_name:
            raise HTTPException(status_code=404, detail="Preset not found")

        config = json.loads(preset["config"]) if isinstance(preset["config"], str) else preset["config"]
        return {"api_key": config.get("api_key")}
    finally:
        await sqlite.close()


@router.post("/models/{model_name}/presets/{preset_id}/list-models")
async def list_available_models(
    model_name: Literal["chat", "embedding", "asr"],
    preset_id: str,
    payload: ModelListRequest,
) -> dict:
    """Fetch available model names using a preset's draft config."""
    sqlite = _get_sqlite_client()
    await sqlite.connect()
    try:
        current_config = await _load_preset_config(
            sqlite,
            model_name=model_name,
            preset_id=preset_id,
        )
    finally:
        await sqlite.close()

    config = _merge_preset_config(current_config, payload.config)
    if _is_ollama_model_list_config(config):
        models = await asyncio.to_thread(_list_ollama_models, config)
    else:
        models = await asyncio.to_thread(_list_openai_compatible_models, config)
    return {"models": models}


@router.patch("/models/{model_name}/presets/{preset_id}")
async def update_preset(
    request: Request,
    model_name: Literal["chat", "embedding", "asr"],
    preset_id: str,
    payload: PresetUpdateRequest,
) -> PresetResponse:
    """Update a preset. Masked API keys are preserved."""
    if model_name == "embedding":
        _raise_if_embedding_reindex_running(request)

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

        new_config = _merge_preset_config(current_config, payload.config)

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
    request: Request,
    model_name: Literal["chat", "embedding", "asr"],
    preset_id: str,
) -> None:
    """Delete a preset. If it was active, fallback to the first remaining preset."""
    if model_name == "embedding":
        _raise_if_embedding_reindex_running(request)

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
    if model_name == "embedding":
        raise HTTPException(
            status_code=409,
            detail=(
                "Embedding active preset cannot be switched directly. "
                "Use /api/settings/models/embedding/presets/{preset_id}/"
                "switch-preview and /switch instead."
            ),
        )

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


@router.post("/models/embedding/presets/{preset_id}/switch-preview")
async def preview_embedding_preset_switch(
    request: Request, preset_id: str
) -> dict:
    _raise_if_embedding_reindex_running(request)

    sqlite = _get_sqlite_client()
    await sqlite.connect()
    try:
        raw_config = await _load_preset_config(
            sqlite,
            model_name="embedding",
            preset_id=preset_id,
        )
    finally:
        await sqlite.close()
    config = _resolve_embedding_config(raw_config)
    return await _preview_embedding_switch(
        request,
        preset_id=preset_id,
        config=config,
    )


@router.post("/models/embedding/presets/{preset_id}/switch-preview-config")
async def preview_embedding_preset_config_switch(
    request: Request,
    preset_id: str,
    payload: EmbeddingSwitchPreviewConfigRequest,
) -> dict:
    _raise_if_embedding_reindex_running(request)

    sqlite = _get_sqlite_client()
    await sqlite.connect()
    try:
        current_config = await _load_preset_config(
            sqlite,
            model_name="embedding",
            preset_id=preset_id,
        )
    finally:
        await sqlite.close()
    config = _resolve_embedding_config(
        _merge_preset_config(current_config, payload.config)
    )
    return await _preview_embedding_switch(
        request,
        preset_id=preset_id,
        config=config,
    )


@router.post("/models/embedding/presets/{preset_id}/switch")
async def switch_embedding_preset(
    request: Request,
    preset_id: str,
    payload: EmbeddingSwitchRequest,
) -> dict:
    sqlite = _get_sqlite_client()
    await sqlite.connect()
    try:
        raw_config = await _load_preset_config(
            sqlite,
            model_name="embedding",
            preset_id=preset_id,
        )
    finally:
        await sqlite.close()
    config = _resolve_embedding_config(raw_config)

    _raise_if_embedding_reindex_running(request)

    preview = await _preview_embedding_switch(
        request,
        preset_id=preset_id,
        config=config,
    )
    if preview["same_dimension"]:
        _raise_if_embedding_reindex_running(request)
        _set_active_embedding_preset_sync(preset_id)
        return {
            **preview,
            "job_id": None,
            "status": "completed",
            "stage": "completed",
        }

    if not payload.confirm_reindex:
        raise HTTPException(
            status_code=409,
            detail=(
                "Embedding dimension change requires confirm_reindex=true "
                "before starting a background reindex job"
            ),
        )

    manager = _get_embedding_reindex_manager(request)
    try:
        started = manager.start_job(
            preset_id=preset_id,
            embedding_client_factory=lambda: _build_embedding_client_for_config(config),
            activate_preset=_set_active_embedding_preset_sync,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    job = started["job"]
    return JSONResponse(
        status_code=202,
        content={
            **preview,
            "job_id": job["id"],
            "status": job["status"],
            "stage": job["stage"],
            "total_documents": job["total_documents"],
            "processed_documents": job["processed_documents"],
            "failed_documents": job["failed_documents"],
            "error": job["error"],
            "started_at": job["started_at"],
            "finished_at": job["finished_at"],
        },
    )


@router.get("/embedding-reindex-jobs/active")
async def get_active_embedding_reindex_job(request: Request) -> dict | None:
    manager = _get_embedding_reindex_manager(request)
    active_job = getattr(manager, "active_job", None)
    if not callable(active_job):
        return None
    return active_job()


@router.get("/embedding-reindex-jobs/{job_id}")
async def get_embedding_reindex_job(request: Request, job_id: str) -> dict:
    manager = _get_embedding_reindex_manager(request)
    job = manager.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Embedding reindex job not found")
    return job
