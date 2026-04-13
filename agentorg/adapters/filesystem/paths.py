"""Path helpers for filesystem adapters."""

from __future__ import annotations

from pathlib import Path

from agentorg.config import Config


def persona_dirs(config: Config) -> tuple[Path, Path]:
    """Return (starter_dir, user_dir) for personas."""
    return config.starter_personas_dir, config.user_personas_dir


def team_dirs(config: Config) -> tuple[Path, Path]:
    """Return (starter_dir, user_dir) for teams."""
    return config.starter_teams_dir, config.user_teams_dir


def skill_dirs(config: Config) -> tuple[Path, Path]:
    """Return (starter_dir, user_dir) for skills."""
    return config.starter_skills_dir, config.user_skills_dir


def scan_subdirs(directory: Path) -> list[str]:
    """List subdirectory names in a directory. Returns empty list if dir doesn't exist."""
    if not directory.is_dir():
        return []
    return sorted(
        d.name for d in directory.iterdir()
        if d.is_dir() and not d.name.startswith(".")
    )


def scan_yaml_files(directory: Path) -> list[str]:
    """List YAML file stems in a directory. Returns empty list if dir doesn't exist."""
    if not directory.is_dir():
        return []
    return sorted(
        f.stem for f in directory.iterdir()
        if f.suffix == ".yaml" and not f.name.startswith(".")
    )
