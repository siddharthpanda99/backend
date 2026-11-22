"""Nexus Runtime Execution Fabric - Runtime Profile Registry.

Maps model IDs to execution profiles (environment, python, adapter, capabilities).
This is the authoritative registry for where each model gets executed.

Profiles are loaded from profiles.yaml which references backends.yaml for
model-specific configurations. This separation allows:
- profiles.yaml: runtime/deployment concerns (venvs, VRAM, resources)
- backends.yaml: model-specific configs (checkpoints, steps, cfg, adapters)
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum
import yaml


def _env(key: str, default: str) -> str:
    value = os.environ.get(key)
    return value if value else default


def _resolve_env_vars(value: Any) -> Any:
    """Recursively resolve ${VAR} and ${VAR:-default} in strings, including nested expressions."""
    if isinstance(value, str):
        import re

        def replace_var(match):
            var_expr = match.group(1)
            if ":-" in var_expr:
                var, default = var_expr.split(":-", 1)
                return _env(var, default)
            return _env(var_expr, "")

        for _ in range(5):
            new_value = re.sub(r"\$\{([^{}]+)\}", replace_var, value)
            if new_value == value:
                break
            value = new_value
        return value
    elif isinstance(value, dict):
        return {k: _resolve_env_vars(v) for k, v in value.items()}
    elif isinstance(value, list):
        return [_resolve_env_vars(v) for v in value]
    return value


def _load_profiles_yaml() -> Dict[str, Any]:
    """Load profiles from YAML file."""
    profiles_path = Path(__file__).parent / "profiles.yaml"
    if not profiles_path.exists():
        # Fallback to default locations
        for path in [
            Path("/opt/nexus/config/profiles.yaml"),
            Path("/data/config/profiles.yaml"),
            Path.cwd() / "profiles.yaml",
        ]:
            if path.exists():
                profiles_path = path
                break
        else:
            return {"profiles": [], "_env_defaults": {}}

    with open(profiles_path) as f:
        data = yaml.safe_load(f)

    # Resolve environment variables in the loaded data
    return _resolve_env_vars(data)


def _load_backends_yaml() -> Dict[str, Any]:
    """Load backend configurations from YAML file."""
    backends_path = (
        Path(__file__).parent.parent
        / "image_processing"
        / "generation"
        / "configs"
        / "backends.yaml"
    )
    if not backends_path.exists():
        return {"backends": []}

    with open(backends_path) as f:
        data = yaml.safe_load(f)

    return _resolve_env_vars(data)


# Load data at module import time
_PROFILES_DATA = _load_profiles_yaml()
_BACKENDS_DATA = _load_backends_yaml()

# Extract environment defaults
_env_defaults = _PROFILES_DATA.get("_env_defaults", {})
_ENVS_ROOT = _env("NEXUS_ENVS_ROOT", _env_defaults.get("NEXUS_ENVS_ROOT", "/opt/nexus/envs"))
_CONTROL_VENV = _env(
    "NEXUS_CONTROL_VENV", _env_defaults.get("NEXUS_CONTROL_VENV", "/opt/nexus/control-venv")
)
_TOOLCHAINS_ROOT = _env(
    "NEXUS_TOOLCHAINS_ROOT", _env_defaults.get("NEXUS_TOOLCHAINS_ROOT", "/opt/nexus/toolchains")
)
_WORKDIR = _env("NEXUS_WORKDIR", _env_defaults.get("NEXUS_WORKDIR", "/opt/nexus"))
_TOOLCHAIN_VENVS = _env("NEXUS_TOOLCHAIN_VENVS", _env_defaults.get("NEXUS_TOOLCHAIN_VENVS", ""))


def _toolchain(toolchain: str, default_env: str, default_python: str):
    """Resolve (environment, python) for a profile's toolchain.

    Docker default: unchanged. When NEXUS_TOOLCHAIN_VENVS is set (repo-local
    toolchains/ tree), workers use <root>/<toolchain>/.venv. The venvs are
    provisioned by the fabric launcher script only -- never shared with the
    backend venv. An explicitly exported NEXUS_IMAGE_PYTHON beats the
    toolchains/ layout for the image toolchain.
    """
    if _TOOLCHAIN_VENVS:
        env = f"{_TOOLCHAIN_VENVS}/{toolchain}"
        return env, f"{env}/.venv/bin/python"
    return default_env, default_python


# Pre-compute toolchain paths for built-in profiles
_acestep_env, _acestep_py = _toolchain(
    "ace-step", f"{_ENVS_ROOT}/acestep", f"{_ENVS_ROOT}/acestep/bin/python"
)
_cosyvoice_env, _cosyvoice_py = _toolchain(
    "cosyvoice", f"{_ENVS_ROOT}/cosyvoice", f"{_ENVS_ROOT}/cosyvoice/bin/python"
)
_fishspeech_env, _fishspeech_py = _toolchain(
    "fish-speech", f"{_ENVS_ROOT}/fish-speech", f"{_ENVS_ROOT}/fish-speech/bin/python"
)
_seedvc_env, _seedvc_py = _toolchain(
    "seed-vc", f"{_ENVS_ROOT}/seed-vc", f"{_ENVS_ROOT}/seed-vc/bin/python"
)

# Image toolchain precedence: explicit NEXUS_IMAGE_PYTHON > toolchains/ layout > Docker envs default
# image-cuda == the NATIVE/torch profile (torch+diffusers, 7000M reservation).
_image_python_override = os.environ.get("NEXUS_IMAGE_PYTHON")
if _image_python_override:
    _image_env, _image_py = _env("NEXUS_IMAGE_ENV", f"{_ENVS_ROOT}/image"), _image_python_override
else:
    _image_env, _image_py = _toolchain(
        "image", f"{_ENVS_ROOT}/image", f"{_ENVS_ROOT}/image/bin/python"
    )

# image-sdcli == the GGUF/Vulkan profile (sd-cli + Vulkan; no torch in the venv).
# sd-cli offloads most weights to system RAM, so the VRAM reservation is small
# enough to coexist with light STT/TTS workers inside the 7000M admission budget.
_image_sdcli_env, _image_sdcli_py = _toolchain(
    "image-sdcli", f"{_ENVS_ROOT}/image-sdcli", f"{_ENVS_ROOT}/image-sdcli/bin/python"
)


class ProfileState(str, Enum):
    ENABLED = "enabled"
    DISABLED = "disabled"
    MAINTENANCE = "maintenance"


@dataclass
class RuntimeProfile:
    profile_id: str
    toolchain: str
    environment: str
    python: str
    adapter: str
    protocol: str = "local-http"
    startup_timeout_seconds: int = 240
    idle_timeout_seconds: int = 600
    max_workers: int = 1
    device: str = "cuda"
    capabilities: List[str] = field(default_factory=list)
    resource_class: str = "gpu_heavy"
    vram_mb: int = 6000
    enabled: bool = True
    state: ProfileState = ProfileState.ENABLED
    healthcheck_type: str = "worker_http"
    healthcheck_path: str = "/health"
    working_directory: str = "/opt/nexus"
    environment_vars: Dict[str, str] = field(default_factory=dict)
    # New fields from YAML
    model_families: List[str] = field(default_factory=list)
    backend_families: List[str] = field(default_factory=list)
    description: str = ""
    description_long: str = ""
    best_configs: List[Dict[str, Any]] = field(default_factory=list)
    best_configs_ref: str = ""
    runtime_requirements: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    tags_internal: List[str] = field(default_factory=dict)
    # Backend linkage
    backend_config: Optional[Dict[str, Any]] = None


class ProfileRegistry:
    """Registry of all runtime profiles and model-to-profile mappings.

    Profiles are loaded from profiles.yaml and linked to backend configs
    from backends.yaml. The registry provides a unified view of both.
    """

    # Backwards compatibility - static profiles as fallback
    PROFILES: Dict[str, RuntimeProfile] = {}
    MODEL_PROFILE_MAP: Dict[str, str] = {}
    _loaded_from_yaml: bool = False

    @classmethod
    def _load_profiles(cls) -> None:
        """Load profiles from YAML and build registry."""
        if cls._loaded_from_yaml:
            return

        cls.PROFILES.clear()
        cls.MODEL_PROFILE_MAP.clear()

        # Load from profiles.yaml
        for profile_data in _PROFILES_DATA.get("profiles", []):
            if not profile_data.get("enabled", True):
                continue

            # Resolve environment variables in profile data
            profile_data = _resolve_env_vars(profile_data)

            # Create profile object
            profile = RuntimeProfile(
                profile_id=profile_data["profile_id"],
                toolchain=profile_data["toolchain"],
                environment=profile_data["environment"],
                python=profile_data["python"],
                adapter=profile_data["adapter"],
                protocol=profile_data.get("protocol", "local-http"),
                startup_timeout_seconds=profile_data.get("startup_timeout_seconds", 240),
                idle_timeout_seconds=profile_data.get("idle_timeout_seconds", 600),
                max_workers=profile_data.get("max_workers", 1),
                device=profile_data.get("device", "cuda"),
                capabilities=profile_data.get("capabilities", []),
                resource_class=profile_data.get("resource_class", "gpu_heavy"),
                vram_mb=profile_data.get("vram_mb", 6000),
                enabled=profile_data.get("enabled", True),
                state=ProfileState(profile_data.get("state", "enabled")),
                healthcheck_type=profile_data.get("healthcheck_type", "worker_http"),
                healthcheck_path=profile_data.get("healthcheck_path", "/health"),
                working_directory=profile_data.get("working_directory", "/opt/nexus"),
                environment_vars=profile_data.get("environment_vars", {}),
                model_families=profile_data.get("model_families", []),
                backend_families=profile_data.get("backend_families", []),
                description=profile_data.get("description", ""),
                description_long=profile_data.get("description_long", ""),
                best_configs=profile_data.get("best_configs", []),
                best_configs_ref=profile_data.get("best_configs_ref", ""),
                runtime_requirements=profile_data.get("runtime_requirements", {}),
                tags=profile_data.get("tags", []),
                tags_internal=profile_data.get("tags_internal", {}),
            )

            # Link to backend config
            backend_families = profile_data.get("backend_families", [])
            backend_configs = {}
            for family in profile_data.get("backend_families", []):
                backend = cls._find_backend_config(family)
                if backend:
                    backend_configs[family] = backend

            if backend_configs:
                profile.backend_config = backend_configs

            cls.PROFILES[profile_data["profile_id"]] = profile

            # Build model -> profile map from backend configs
            for family, backend in backend_configs.items():
                if isinstance(backend, dict) and "id" in backend:
                    cls.MODEL_PROFILE_MAP[backend["id"]] = profile_data["profile_id"]
                # Also map by family name
                for model_id, profile_id in cls._get_model_ids_for_family(family).items():
                    cls.MODEL_PROFILE_MAP[model_id] = profile_data["profile_id"]

            # Build model -> profile map from backend configs
            for family, backend in backend_configs.items():
                if isinstance(backend, dict) and "id" in backend:
                    cls.MODEL_PROFILE_MAP[backend["id"]] = profile_data["profile_id"]
                # Also map by family name for all models in that family
                for model_id, _ in cls._get_model_ids_for_family(family).items():
                    cls.MODEL_PROFILE_MAP[model_id] = profile_data["profile_id"]

        # All model-to-profile mappings are now derived from profiles.yaml (backend_families)
        # and backends.yaml (model families). No hardcoded static_map needed.
        # Special cases (echo, ace-step, etc.) should have their own profile entries
        # in profiles.yaml with appropriate backend_families.

        cls._loaded_from_yaml = True

    @classmethod
    def _find_backend_config(cls, family: str) -> Optional[Dict[str, Any]]:
        """Find backend config by family name or id."""
        backends = _BACKENDS_DATA.get("backends", [])
        for backend in backends:
            if backend.get("family") == family or backend.get("id") == family:
                return backend
        return None

    @classmethod
    def _get_model_ids_for_family(cls, family: str) -> Dict[str, str]:
        """Get model IDs that belong to a backend family."""
        backends = _BACKENDS_DATA.get("backends", [])
        result = {}
        for backend in backends:
            if backend.get("family") == family or backend.get("id") == family:
                result[backend["id"]] = True
        return result

    @classmethod
    def _ensure_loaded(cls) -> None:
        if not cls._loaded_from_yaml:
            cls._load_profiles()

    @classmethod
    def get_profile(cls, profile_id: str) -> Optional[RuntimeProfile]:
        cls._ensure_loaded()
        return cls.PROFILES.get(profile_id)

    @classmethod
    def get_all_profiles(cls) -> List[RuntimeProfile]:
        cls._ensure_loaded()
        return list(cls.PROFILES.values())

    @classmethod
    def get_enabled_profiles(cls) -> List[RuntimeProfile]:
        cls._ensure_loaded()
        return [p for p in cls.PROFILES.values() if p.enabled]

    @classmethod
    def get_profile_for_model(cls, model_id: str) -> Optional[RuntimeProfile]:
        cls._ensure_loaded()
        profile_id = cls.MODEL_PROFILE_MAP.get(model_id)
        if profile_id:
            return cls.get_profile(profile_id)

        # Fallback 1: Check engine aliases from image worker if applicable
        try:
            from common_lib.nexus_workers.image_gen import ENGINE_ALIASES

            aliased = ENGINE_ALIASES.get(model_id)
            if aliased:
                # Check if aliased engine is a profile ID directly
                if aliased in cls.MODEL_PROFILE_MAP:
                    return cls.get_profile(cls.MODEL_PROFILE_MAP[aliased])
                # Check if aliased engine matches a profile's backend_families
                for profile in cls.PROFILES.values():
                    if aliased in profile.backend_families:
                        return profile
        except Exception:
            pass

        # Fallback 2: Check standard image model families by substring
        mid_lower = model_id.lower()
        if "moss" in mid_lower:
            # Check if it's an INT8 ConvRot model (should use native ComfyUI)
            if any(x in mid_lower for x in ["int8", "convrot", "fucktoy", "realvision"]):
                if "image-cuda" in cls.PROFILES:
                    return cls.get_profile("image-cuda")
            if "image-sdcli" in cls.PROFILES:
                return cls.get_profile("image-sdcli")
        if any(
            term in mid_lower
            for term in [
                "ming",
                "krea",
                "qwen",
                "zimage",
                "z-image",
                "sdxl",
                "realvis",
                "pony",
                "animagine",
                "sd15",
            ]
        ):
            if "image-cuda" in cls.PROFILES:
                return cls.get_profile("image-cuda")

        return None

    @classmethod
    def get_all_model_ids(cls) -> List[str]:
        cls._ensure_loaded()
        return list(cls.MODEL_PROFILE_MAP.keys())

    @classmethod
    def get_backend_config(cls, model_id: str) -> Optional[Dict[str, Any]]:
        """Get the backend config for a model ID."""
        cls._ensure_loaded()
        backends = _BACKENDS_DATA.get("backends", [])
        for backend in backends:
            if backend.get("id") == model_id:
                return backend
        # Try by family
        for backend in backends:
            if backend.get("id") == model_id or backend.get("family") == model_id:
                return backend
        return None

    @classmethod
    def get_best_config(
        cls, profile_id: str, config_name: str = "default"
    ) -> Optional[Dict[str, Any]]:
        """Get a best config by name from the profile's referenced backends.yaml."""
        cls._ensure_loaded()
        profile = cls.get_profile(profile_id)
        if not profile:
            return None

        # Try to find config in backend configs
        if profile.backend_config:
            for family, backend in profile.backend_config.items():
                best_configs = backend.get("best_configs", [])
                for config in best_configs:
                    if config.get("name") == config_name:
                        return config
        return None

    @classmethod
    def reload(cls) -> None:
        """Reload profiles from YAML (useful for development)."""
        global _PROFILES_DATA, _BACKENDS_DATA
        _PROFILES_DATA = _load_profiles_yaml()
        _BACKENDS_DATA = _load_backends_yaml()
        cls._loaded_from_yaml = False
        cls._load_profiles()


# Trigger initial load
ProfileRegistry._load_profiles()
