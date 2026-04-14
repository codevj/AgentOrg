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

_DEFAULT_SETTINGS = {
    "default_backend": "claude",
    "default_team": "product-delivery",
    "reflection": "auto",
    "condense_after": 5,
    "scratch_dir": "~/.agent-org/scratch",
}


class NotInitializedError(RuntimeError):
    """Raised when AgentOrg has not been initialized (no active org)."""


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

        Resolution:
          - If AGENT_ORG_HOME env var is set, use it directly as org_home (test-friendly).
          - Otherwise, require an active org (.active-org file) and resolve to
            <root>/orgs/<name>.
        """
        # Start with defaults
        settings = dict(_DEFAULT_SETTINGS)

        # Resolve org_home. Env var takes precedence (used for testing).
        env_home = os.environ.get("AGENT_ORG_HOME")
        if env_home:
            org_home = Path(env_home).expanduser()
        else:
            # Must have an active org
            active_org = get_active_org()  # raises NotInitializedError if missing
            org_home = _root_dir() / "orgs" / active_org

        # Layer 2: settings file at org_home (if it exists)
        settings_path = org_home / _SETTINGS_FILENAME
        if settings_path.is_file():
            file_settings = _load_settings_file(settings_path)
            settings.update({k: v for k, v in file_settings.items() if v is not None})

        # Layer 1: environment variable override for backend
        if env_backend := os.environ.get("AGENT_ORG_BACKEND"):
            settings["default_backend"] = env_backend

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
    def user_templates_dir(self) -> Path:
        return self.org_home / "templates"

    @property
    def knowledge_dir(self) -> Path:
        return self.org_home / "knowledge"

    @property
    def runs_dir(self) -> Path:
        return self.org_home / "runs"

    @property
    def projects_dir(self) -> Path:
        return self.org_home / "projects"


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
    # Preserve any extra keys (like condense_after) already in the file
    existing: dict = {}
    if config.settings_file.is_file():
        existing = yaml.safe_load(config.settings_file.read_text()) or {}
    data = {
        **existing,
        "default_backend": config.default_backend,
        "default_team": config.default_team,
        "reflection": config.reflection,
    }
    # org_home is no longer persisted — it's resolved at load time from the
    # active org name (or AGENT_ORG_HOME env var for tests).
    data.pop("org_home", None)
    config.settings_file.write_text(yaml.dump(data, default_flow_style=False, sort_keys=False))


def get_reflection_mode(config: Config) -> ReflectionMode:
    """Read reflection mode from the loaded config."""
    try:
        return ReflectionMode(config.reflection)
    except ValueError:
        return ReflectionMode.AUTO


def set_reflection_mode(config: Config, mode: ReflectionMode) -> None:
    """Write reflection mode to settings file, preserving other settings."""
    data = _read_settings(config)
    data["reflection"] = mode.value
    data.pop("auto_reflect", None)  # remove legacy key
    _write_settings(config, data)


# ── Org switching ──

def _root_dir() -> Path:
    """The root agent-org directory (parent of named orgs)."""
    return Path(os.environ.get("AGENT_ORG_ROOT", Path.home() / ".agent-org"))


def _active_org_file() -> Path:
    return _root_dir() / _ACTIVE_ORG_FILENAME


def is_initialized() -> bool:
    """Return True if AgentOrg is initialized (active org or AGENT_ORG_HOME env var)."""
    if os.environ.get("AGENT_ORG_HOME"):
        return True
    f = _active_org_file()
    if not f.is_file():
        return False
    return bool(f.read_text().strip())


def get_active_org() -> str:
    """Get the name of the active org.

    Raises NotInitializedError if no .active-org file exists. Callers that
    need graceful handling should check is_initialized() first, or set the
    AGENT_ORG_HOME env var (which bypasses the org lookup entirely in
    Config.load).
    """
    active_file = _active_org_file()
    if active_file.is_file():
        name = active_file.read_text().strip()
        if name:
            return name
    raise NotInitializedError(
        "AgentOrg is not initialized. Run 'fleet init' to create your first org."
    )


def set_active_org(name: str) -> Path:
    """Switch to a named org. Creates it if it doesn't exist. Returns the org home."""
    root = _root_dir()
    org_dir = root / "orgs" / name
    org_dir.mkdir(parents=True, exist_ok=True)
    root.mkdir(parents=True, exist_ok=True)
    _active_org_file().write_text(name)
    return org_dir


def list_orgs() -> list[str]:
    """List all named orgs."""
    orgs_dir = _root_dir() / "orgs"
    if not orgs_dir.is_dir():
        return []
    return sorted(d.name for d in orgs_dir.iterdir() if d.is_dir())


def detect_legacy_layout() -> bool:
    """True if root has settings.yaml but no .active-org (pre-named-org layout)."""
    root = _root_dir()
    return (root / _SETTINGS_FILENAME).is_file() and not _active_org_file().is_file()


def migrate_legacy_to_named_org(name: str) -> Path:
    """Move root-level org files into orgs/<name>/ and mark it active.

    Returns the new org directory.
    """
    import shutil

    root = _root_dir()
    target = root / "orgs" / name
    target.mkdir(parents=True, exist_ok=True)

    # Folders and files to move from root to orgs/<name>/
    candidates = [
        "settings.yaml",
        "personas",
        "teams",
        "skills",
        "knowledge",
        "runs",
        "projects",
        "templates",
    ]
    for entry in candidates:
        src = root / entry
        if not src.exists():
            continue
        dst = target / entry
        if dst.exists():
            # Don't clobber — skip
            continue
        shutil.move(str(src), str(dst))

    _active_org_file().write_text(name)
    return target


# ── Settings helpers ──


def _read_settings(config: Config) -> dict:
    """Read settings.yaml, migrating legacy dot-files if present."""
    settings_file = config.org_home / _SETTINGS_FILENAME
    data: dict = {}
    if settings_file.is_file():
        data = yaml.safe_load(settings_file.read_text()) or {}

    # Migrate legacy .active-backend dot-file
    legacy_backend = config.org_home / ".active-backend"
    if legacy_backend.is_file() and "active_backend" not in data:
        value = legacy_backend.read_text().strip()
        if value:
            data["active_backend"] = value
            _write_settings(config, data)
        legacy_backend.unlink()

    # Migrate legacy .active-project dot-file
    legacy_project = config.org_home / ".active-project"
    if legacy_project.is_file() and "active_project" not in data:
        value = legacy_project.read_text().strip()
        if value:
            data["active_project"] = value
            _write_settings(config, data)
        legacy_project.unlink()

    return data


def _write_settings(config: Config, data: dict) -> None:
    """Write settings.yaml, preserving ordering."""
    config.org_home.mkdir(parents=True, exist_ok=True)
    settings_file = config.org_home / _SETTINGS_FILENAME
    settings_file.write_text(yaml.dump(data, default_flow_style=False, sort_keys=False))


# ── Project switching ──


def get_active_project(config: Config) -> str | None:
    """Return active project id, or None if no project is active."""
    data = _read_settings(config)
    value = data.get("active_project")
    return value if value else None


def set_active_project(config: Config, project_id: str) -> None:
    data = _read_settings(config)
    data["active_project"] = project_id
    _write_settings(config, data)


def clear_active_project(config: Config) -> None:
    data = _read_settings(config)
    if "active_project" in data:
        data.pop("active_project")
        _write_settings(config, data)


# ── Backend switching ──


def get_active_backend(config: Config) -> str:
    """Return the active backend name.

    Resolution: active_backend in settings.yaml → env var → config default.
    """
    data = _read_settings(config)
    value = data.get("active_backend")
    if value:
        return value
    return config.default_backend


def set_active_backend(config: Config, name: str) -> None:
    """Persist *name* as the active backend in settings.yaml."""
    data = _read_settings(config)
    data["active_backend"] = name
    _write_settings(config, data)


def get_condense_after(config: Config) -> int:
    """Read condense_after from settings file. Defaults to 5."""
    data = _read_settings(config)
    val = data.get("condense_after", _DEFAULT_SETTINGS["condense_after"])
    try:
        return int(val)
    except (TypeError, ValueError):
        return _DEFAULT_SETTINGS["condense_after"]


def set_condense_after(config: Config, value: int) -> None:
    data = _read_settings(config)
    data["condense_after"] = value
    _write_settings(config, data)


def get_scratch_dir(config: Config) -> Path:
    """Read scratch_dir from settings. Defaults to ~/.agent-org/scratch."""
    data = _read_settings(config)
    raw = data.get("scratch_dir", _DEFAULT_SETTINGS["scratch_dir"])
    return Path(raw).expanduser()


def set_scratch_dir(config: Config, path: str) -> None:
    data = _read_settings(config)
    data["scratch_dir"] = path
    _write_settings(config, data)
