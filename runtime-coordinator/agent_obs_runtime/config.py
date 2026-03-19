"""Configuration loading for the runtime coordinator."""

from __future__ import annotations

import ast
import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from .mode import CoordinationMode

ENV_PREFIX = "AGENT_OBS_"
DEFAULT_CONFIG_FILE_ENV = f"{ENV_PREFIX}CONFIG_FILE"
DEFAULT_HEURISTICS = [
    "tracer_provider",
    "span_processors",
    "env_ownership",
    "known_indicators",
]


@dataclass(slots=True)
class RuntimeConfig:
    """Runtime coordinator settings loaded from env vars and an optional file."""

    mode: CoordinationMode | None = None
    diagnostics_level: str = "basic"
    enabled_heuristics: list[str] = field(default_factory=lambda: list(DEFAULT_HEURISTICS))
    enabled_patchers: list[str] = field(default_factory=list)
    suppression_settings: dict[str, Any] = field(default_factory=dict)
    config_file: str | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["mode"] = self.mode.value if self.mode else None
        return payload


@dataclass(slots=True)
class LoadedConfig:
    """Config plus metadata gathered while loading it."""

    config: RuntimeConfig
    config_source: str
    warnings: list[str] = field(default_factory=list)



def load_config() -> LoadedConfig:
    """Load configuration from env vars and an optional JSON/TOML-like file."""

    warnings: list[str] = []
    file_path = os.getenv(DEFAULT_CONFIG_FILE_ENV)
    file_values: dict[str, Any] = {}
    source = "environment"

    if file_path:
        try:
            file_values = _read_config_file(Path(file_path))
            source = f"environment + {file_path}"
        except Exception as exc:  # pragma: no cover - defensive path
            warnings.append(f"failed_to_load_config_file:{file_path}:{exc}")
            source = f"environment (config file load failed: {file_path})"

    mode = _parse_mode(_read_setting("mode", file_values))
    diagnostics_level = str(_read_setting("diagnostics_level", file_values, default="basic"))
    enabled_heuristics = _parse_list(_read_setting("enabled_heuristics", file_values, default=DEFAULT_HEURISTICS))
    enabled_patchers = _parse_list(_read_setting("enabled_patchers", file_values, default=[]))
    suppression_settings = _parse_mapping(_read_setting("suppression_settings", file_values, default={}))

    return LoadedConfig(
        config=RuntimeConfig(
            mode=mode,
            diagnostics_level=diagnostics_level,
            enabled_heuristics=enabled_heuristics,
            enabled_patchers=enabled_patchers,
            suppression_settings=suppression_settings,
            config_file=file_path,
        ),
        config_source=source,
        warnings=warnings,
    )



def _read_setting(name: str, file_values: dict[str, Any], default: Any = None) -> Any:
    env_name = f"{ENV_PREFIX}{name.upper()}"
    if env_name in os.environ:
        return os.environ[env_name]
    if name in file_values:
        return file_values[name]
    return default



def _read_config_file(path: Path) -> dict[str, Any]:
    raw = path.read_text(encoding="utf-8")
    if path.suffix == ".json":
        data = json.loads(raw)
    else:
        data = _parse_simple_toml(raw)
    if not isinstance(data, dict):
        raise ValueError("config file must deserialize to a mapping")
    return data



def _parse_mode(value: Any) -> CoordinationMode | None:
    if value is None or value == "":
        return None
    if isinstance(value, CoordinationMode):
        return value
    return CoordinationMode(str(value).strip().upper())



def _parse_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return [item.strip() for item in str(value).split(",") if item.strip()]



def _parse_mapping(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, dict):
        return value
    text = str(value).strip()
    if not text:
        return {}
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return {"raw": text}
    if not isinstance(parsed, dict):
        return {"value": parsed}
    return parsed



def _parse_simple_toml(raw: str) -> dict[str, Any]:
    result: dict[str, Any] = {}
    current: dict[str, Any] = result

    for line in raw.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("[") and line.endswith("]"):
            table_name = line[1:-1].strip()
            nested = result.setdefault(table_name, {})
            if not isinstance(nested, dict):
                raise ValueError(f"table {table_name} conflicts with scalar value")
            current = nested
            continue
        if "=" not in line:
            raise ValueError(f"invalid config line: {line}")
        key, raw_value = [part.strip() for part in line.split("=", 1)]
        current[key] = _parse_simple_value(raw_value)

    return result



def _parse_simple_value(raw_value: str) -> Any:
    normalized = raw_value.strip()
    if normalized.lower() in {"true", "false"}:
        return normalized.lower() == "true"
    if normalized.startswith('"') or normalized.startswith("[") or normalized.startswith("{"):
        return ast.literal_eval(normalized)
    try:
        return int(normalized)
    except ValueError:
        return normalized
