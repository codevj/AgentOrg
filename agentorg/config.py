"""Configuration — paths, defaults, settings file loading."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

import yaml


class ReflectionMode(Enum):
    """Controls what happens after --exec runs.

    AUTO    — reflect automatically, write learnings without asking
    REVIEW  — reflect, but show learnings for approval before saving
    OFF     — no automatic reflection
    """

    AUTO = "auto"
    REVIEW = "review"
    OFF = "off"


def _package_dir() -> Path:
    """Return the agentorg package directory (where starters/ lives)."""
    return Path(__file__).parent


_SETTINGS_FILENAME = "settings.yaml"
_ACTIVE_ORG_FILENAME = ".active-org"
_AGENT_ORG_ROOT = Path.home() / ".agent-org"

_DEFAULT_SETTINGS = {
    "org_home": "~/.agent-org",
    "default_backend": "claude",
    "default_team": "product-delivery",
    "reflection": "auto",
}


@dataclass(frozen=True)
class Config:
    """Immutable configuration resolved from: settings file → env vars → defaults.

    Resolution order (first wins):
      1. Environment variables (AGENT_ORG_HOME, AGENT_ORG_BACKEND)
      2. Settings file (~/.agent-org/settings.yaml)
      3. Built-in defaults
    """

    starters_dir: Path
    org_home: Path
    default_backend: str = "claude"
    default_team: str = "product-delivery"
    reflection: str = "auto"

    @classmethod
    def load(cls) -> Config:
        """Load config from settings file, environment, and defaults.

        Resolution: env var → active org → settings file → defaults.
        """
        # Start with defaults
        settings = dict(_DEFAULT_SETTINGS)

        # Check for active named org (e.g., "personal" or "work")
        active_org = get_active_org()
        if active_org:
            settings["org_home"] = str(_root_dir() / "orgs" / active_org)

        # Layer 2: settings file (if it exists)
        settings_path = _find_settings_file()
        if settings_path and settings_path.is_file():
            file_settings = _load_settings_file(settings_path)
            settings.update({k: v for k, v in file_settings.items() if v is not None})

        # If active org is set, it overrides the settings file org_home
        if active_org:
            settings["org_home"] = str(_root_dir() / "orgs" / active_org)

        # Layer 1: environment variables (highest priority)
        if env_home := os.environ.get("AGENT_ORG_HOME"):
            settings["org_home"] = env_home
        if env_backend := os.environ.get("AGENT_ORG_BACKEND"):
            settings["default_backend"] = env_backend

        org_home = Path(settings["org_home"]).expanduser()

        # Migrate legacy auto_reflect boolean to reflection mode string
        raw_reflection = settings.get("reflection", settings.get("auto_reflect", "auto"))
        if isinstance(raw_reflection, bool):
            raw_reflection = "auto" if raw_reflection else "off"

        return cls(
            starters_dir=_package_dir() / "starters",
            org_home=org_home,
            default_backend=settings.get("default_backend", "claude"),
            default_team=settings.get("default_team", "product-delivery"),
            reflection=raw_reflection,
        )

    @property
    def settings_file(self) -> Path:
        return self.org_home / _SETTINGS_FILENAME

    # ── Starter paths (read-only reference) ──

    @property
    def starter_personas_dir(self) -> Path:
        return self.starters_dir / "personas"

    @property
    def starter_teams_dir(self) -> Path:
        return self.starters_dir / "teams"

    @property
    def starter_skills_dir(self) -> Path:
        return self.starters_dir / "skills"

    @property
    def contracts_dir(self) -> Path:
        return self.starters_dir / "contracts"

    @property
    def policies_dir(self) -> Path:
        return self.starters_dir / "policies"

    # ── User paths (writable, ~/.agent-org/) ──

    @property
    def user_personas_dir(self) -> Path:
        return self.org_home / "personas"

    @property
    def user_teams_dir(self) -> Path:
        return self.org_home / "teams"

    @property
    def user_skills_dir(self) -> Path:
        return self.org_home / "skills"

    @property
    def knowledge_dir(self) -> Path:
        return self.org_home / "knowledge"

    @property
    def runs_dir(self) -> Path:
        return self.org_home / "runs"

    @property
    def projects_dir(self) -> Path:
        return self.org_home / "projects"


def _find_settings_file() -> Path | None:
    """Find settings.yaml — check env-based home first, then default."""
    if env_home := os.environ.get("AGENT_ORG_HOME"):
        return Path(env_home) / _SETTINGS_FILENAME
    return Path.home() / ".agent-org" / _SETTINGS_FILENAME


def _load_settings_file(path: Path) -> dict:
    """Load settings from YAML file."""
    try:
        data = yaml.safe_load(path.read_text())
        return data if isinstance(data, dict) else {}
    except (yaml.YAMLError, OSError):
        return {}


def save_settings(config: Config) -> None:
    """Write current settings to the settings file."""
    config.org_home.mkdir(parents=True, exist_ok=True)
    data = {
        "org_home": str(config.org_home),
        "default_backend": config.default_backend,
        "default_team": config.default_team,
        "reflection": config.reflection,
    }
    config.settings_file.write_text(yaml.dump(data, default_flow_style=False, sort_keys=False))


def get_reflection_mode(config: Config) -> ReflectionMode:
    """Read reflection mode from the loaded config."""
    try:
        return ReflectionMode(config.reflection)
    except ValueError:
        return ReflectionMode.AUTO


def set_reflection_mode(config: Config, mode: ReflectionMode) -> None:
    """Write reflection mode to settings file, preserving other settings."""
    settings_file = config.org_home / _SETTINGS_FILENAME
    config.org_home.mkdir(parents=True, exist_ok=True)
    data: dict = {}
    if settings_file.is_file():
        data = yaml.safe_load(settings_file.read_text()) or {}
    data["reflection"] = mode.value
    # Remove legacy key if present
    data.pop("auto_reflect", None)
    settings_file.write_text(yaml.dump(data, default_flow_style=False, sort_keys=False))


# ── Org switching ──

def _root_dir() -> Path:
    """The root agent-org directory (parent of named orgs)."""
    return Path(os.environ.get("AGENT_ORG_ROOT", _AGENT_ORG_ROOT))


def get_active_org() -> str | None:
    """Get the name of the active org, or None for default."""
    active_file = _root_dir() / _ACTIVE_ORG_FILENAME
    if active_file.is_file():
        name = active_file.read_text().strip()
        return name if name else None
    return None


def set_active_org(name: str) -> Path:
    """Switch to a named org. Creates it if it doesn't exist. Returns the org home."""
    root = _root_dir()
    org_dir = root / "orgs" / name
    org_dir.mkdir(parents=True, exist_ok=True)
    active_file = root / _ACTIVE_ORG_FILENAME
    root.mkdir(parents=True, exist_ok=True)
    active_file.write_text(name)
    return org_dir


def clear_active_org() -> None:
    """Switch back to the default org."""
    active_file = _root_dir() / _ACTIVE_ORG_FILENAME
    if active_file.is_file():
        active_file.unlink()


def list_orgs() -> list[str]:
    """List all named orgs."""
    orgs_dir = _root_dir() / "orgs"
    if not orgs_dir.is_dir():
        return []
    return sorted(d.name for d in orgs_dir.iterdir() if d.is_dir())


# ── Project switching ──


def get_active_project(config: Config) -> str | None:
    """Return active project id, or None if no project is active."""
    pointer = config.org_home / ".active-project"
    if pointer.is_file():
        value = pointer.read_text().strip()
        return value if value else None
    return None


def set_active_project(config: Config, project_id: str) -> None:
    """Set the active project pointer."""
    config.org_home.mkdir(parents=True, exist_ok=True)
    (config.org_home / ".active-project").write_text(project_id + "\n")


def clear_active_project(config: Config) -> None:
    """Clear the active project pointer."""
    pointer = config.org_home / ".active-project"
    if pointer.is_file():
        pointer.unlink()


# ── Backend switching ──


def get_active_backend(config: Config) -> str:
    """Return the active backend name.

    Resolution: .active-backend file → env var → config default.
    """
    pointer = config.org_home / ".active-backend"
    if pointer.is_file():
        value = pointer.read_text().strip()
        if value:
            return value
    return config.default_backend


def set_active_backend(config: Config, name: str) -> None:
    """Persist *name* as the active backend."""
    config.org_home.mkdir(parents=True, exist_ok=True)
    (config.org_home / ".active-backend").write_text(name + "\n")
