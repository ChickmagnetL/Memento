"""Read-modify-write persistence for config.local.yaml model settings.

Only the models section is managed here. None values mean "keep the
existing value" so the API can accept partial updates (e.g. masked keys).
"""

from pathlib import Path

import yaml


class ConfigStore:
    def __init__(self, config_path: Path | str) -> None:
        self.config_path = Path(config_path)

    def _load(self) -> dict:
        if not self.config_path.exists():
            return {}
        return yaml.safe_load(self.config_path.read_text(encoding="utf-8")) or {}

    def update_models(self, models_update: dict) -> None:
        """Merge model config updates into config.local.yaml."""
        data = self._load()
        models = data.setdefault("models", {})
        for model_name, fields in models_update.items():
            section = models.setdefault(model_name, {})
            for key, value in fields.items():
                if value is not None:
                    section[key] = value
        self.config_path.write_text(
            yaml.safe_dump(data, allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )
