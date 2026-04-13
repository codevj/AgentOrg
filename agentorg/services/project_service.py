"""Project service — create, list, scaffold, and manage projects."""

from __future__ import annotations

import yaml
from pathlib import Path

from agentorg.config import Config, clear_active_project, get_active_project, set_active_project
from agentorg.domain.models import Project


def _read_project_config(root: Path) -> dict:
    """Read project.yaml from a project directory."""
    config_file = root / "project.yaml"
    if config_file.is_file():
        return yaml.safe_load(config_file.read_text()) or {}
    return {}


def _write_project_config(root: Path, data: dict) -> None:
    """Write project.yaml to a project directory."""
    (root / "project.yaml").write_text(yaml.dump(data, default_flow_style=False))


def _load_project(project_id: str, root: Path) -> Project:
    """Load a Project from its directory."""
    data = _read_project_config(root)
    raw_paths = data.get("repos", [])
    repo_paths = [Path(p).expanduser() for p in raw_paths]
    return Project(id=project_id, root=root, repo_paths=repo_paths)


class ProjectService:
    """Manages project lifecycle — create, list, activate, deactivate."""

    def __init__(self, config: Config) -> None:
        self._config = config

    def create(self, project_id: str, repo_path: Path | None = None) -> Project:
        """Create a new project with scaffolded directories."""
        root = self._config.projects_dir / project_id
        if root.exists():
            raise ValueError(f"Project already exists: {project_id}")

        # Scaffold directories
        (root / "context").mkdir(parents=True)
        (root / "commands").mkdir()
        (root / "runbooks").mkdir()
        (root / "skills").mkdir()
        (root / "knowledge").mkdir()
        (root / "tasks").mkdir()

        # Scaffold starter files
        (root / "context" / "architecture.md").write_text(
            "# Architecture\n\nDescribe how this system is structured.\n"
        )
        (root / "context" / "domain-glossary.md").write_text(
            "# Domain Glossary\n\nTerms your team should know.\n"
        )
        (root / "commands" / "build-test-lint.md").write_text(
            "# Build, Test, Lint\n\nValidation commands for this project.\n\n"
            "```bash\n# Build\n\n# Test\n\n# Lint\n```\n"
        )
        (root / "runbooks" / "common-failures.md").write_text(
            "# Common Failures\n\nKnown issues and workarounds.\n"
        )
        (root / "knowledge" / "learnings.md").write_text(
            "# Project Learnings\n\n"
            "_No runs yet. Learnings will appear here after tasks are run in this project._\n"
        )

        # Save project config with repo path
        repo_paths = [str(repo_path.resolve())] if repo_path else []
        _write_project_config(root, {"repos": repo_paths})

        return Project(id=project_id, root=root, repo_paths=[repo_path.resolve()] if repo_path else [])

    def add_repo(self, project_id: str, repo_path: Path) -> Project:
        """Add a repo path to an existing project."""
        project = self.get(project_id)
        if project is None:
            raise ValueError(f"Project not found: {project_id}")

        resolved = repo_path.resolve()
        if resolved in project.repo_paths:
            return project  # already there

        data = _read_project_config(project.root)
        repos = data.get("repos", [])
        repos.append(str(resolved))
        data["repos"] = repos
        _write_project_config(project.root, data)

        return _load_project(project_id, project.root)

    def list_projects(self) -> list[Project]:
        """List all projects in the active org."""
        projects_dir = self._config.projects_dir
        if not projects_dir.is_dir():
            return []
        result = []
        for d in sorted(projects_dir.iterdir()):
            if d.is_dir() and not d.name.startswith("."):
                result.append(_load_project(d.name, d))
        return result

    def get(self, project_id: str) -> Project | None:
        """Get a project by id."""
        root = self._config.projects_dir / project_id
        if not root.is_dir():
            return None
        return _load_project(project_id, root)

    def get_active(self) -> Project | None:
        """Get the currently active project, or None."""
        pid = get_active_project(self._config)
        if pid is None:
            return None
        return self.get(pid)

    def activate(self, project_id: str) -> Project:
        """Set a project as active."""
        project = self.get(project_id)
        if project is None:
            raise ValueError(f"Project not found: {project_id}")
        set_active_project(self._config, project_id)
        return project

    def create_task(self, task_name: str) -> Path:
        """Scaffold a task spec in the active project's tasks/ directory.

        Returns the path to the created file.
        """
        active = self.get_active()
        if active is None:
            raise ValueError("No active project. Use: fleet project use <id>")

        slug = task_name.lower().replace(" ", "-")
        task_file = active.root / "tasks" / f"{slug}.md"
        if task_file.exists():
            raise ValueError(f"Task spec already exists: {task_file}")

        title = task_name.replace("-", " ").title()
        task_file.write_text(
            f"# Task: {title}\n"
            "\n"
            "## Problem\n"
            "\n"
            "What's wrong or missing? Why does this matter?\n"
            "\n"
            "## Solution\n"
            "\n"
            "What should be built? High-level approach.\n"
            "\n"
            "## Rabbit Holes\n"
            "\n"
            "- Things to avoid or not over-engineer\n"
            "\n"
            "## No-gos\n"
            "\n"
            "- Hard boundaries — what must NOT change\n"
            "\n"
            "## Acceptance Criteria\n"
            "\n"
            "- [ ] First criterion\n"
            "- [ ] Second criterion\n"
            "\n"
            "## Validation Commands\n"
            "\n"
            "```bash\n"
            "# Commands the tester should run\n"
            "```\n"
        )
        return task_file

    def deactivate(self) -> None:
        """Clear the active project."""
        clear_active_project(self._config)
