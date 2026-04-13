"""Tests for project context integration in RunService."""

from pathlib import Path
from unittest.mock import MagicMock

from agentorg.adapters.rendering.jinja_renderer import JinjaRenderer
from agentorg.domain.models import Budget, Gates, Persona, Team
from agentorg.services.run_service import RunService, _read_project_files


def _make_service(renderer=None) -> RunService:
    """Create a RunService with mock dependencies."""
    persona_repo = MagicMock()
    team_repo = MagicMock()
    skill_repo = MagicMock()
    policy_repo = MagicMock()
    knowledge_store = MagicMock()
    run_store = MagicMock()
    reflect_service = MagicMock()

    if renderer is None:
        renderer = JinjaRenderer()

    # Configure mocks
    persona = Persona(
        id="developer",
        raw_content="## Mission\n\nWrite great code.",
        mission="Write great code.",
    )
    persona_repo.get.return_value = persona

    team = Team(
        id="product-delivery",
        persona_ids=["developer"],
        governance_profile="quality_first",
        gates=Gates(),
        budget=Budget(),
    )
    team_repo.get.return_value = team
    knowledge_store.persona_learnings.return_value = None
    knowledge_store.org_learnings.return_value = None
    knowledge_store.team_learnings.return_value = None
    policy_repo.get_governance.return_value = None

    return RunService(
        persona_repo, team_repo, skill_repo, policy_repo, knowledge_store,
        run_store, renderer, reflect_service,
    )


def test_build_team_prompt_without_project():
    svc = _make_service()
    prompt = svc.build_team_prompt("product-delivery", "Fix the bug.")
    assert "Fix the bug" in prompt
    assert "Project Context" not in prompt
    assert "Project Knowledge" not in prompt
    assert "Project Skills" not in prompt


def test_build_team_prompt_with_project(tmp_path: Path):
    # Set up project directory structure
    project_root = tmp_path / "my-project"
    (project_root / "context").mkdir(parents=True)
    (project_root / "context" / "arch.md").write_text("# Arch\n\nWe use microservices.\n")
    (project_root / "commands").mkdir()
    (project_root / "commands" / "test.md").write_text("# Test\n\n```bash\npytest\n```\n")
    (project_root / "knowledge").mkdir()
    (project_root / "knowledge" / "learnings.md").write_text(
        "# Learnings\n\n- Always check error handling\n"
    )
    (project_root / "skills").mkdir()
    skill_dir = project_root / "skills" / "deploy"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text("---\nname: deploy\n---\n\n# Deploy\n\nRun deploy.sh\n")

    svc = _make_service()
    prompt = svc.build_team_prompt("product-delivery", "Fix the bug.", project_root=project_root)

    assert "Project Context" in prompt
    assert "microservices" in prompt
    assert "Project Commands" in prompt
    assert "pytest" in prompt
    assert "Project Knowledge" in prompt
    assert "error handling" in prompt
    assert "Project Skills" in prompt
    assert "deploy.sh" in prompt


def test_build_solo_prompt_without_project():
    svc = _make_service()
    prompt = svc.build_solo_prompt("Fix the bug.")
    assert "Fix the bug" in prompt
    assert "Project Context" not in prompt


def test_build_solo_prompt_with_project(tmp_path: Path):
    project_root = tmp_path / "my-project"
    (project_root / "context").mkdir(parents=True)
    (project_root / "context" / "arch.md").write_text("# Arch\n\nMonolith architecture.\n")

    svc = _make_service()
    prompt = svc.build_solo_prompt("Fix the bug.", project_root=project_root)

    assert "Project Context" in prompt
    assert "Monolith architecture" in prompt


def test_read_project_files_empty_dir(tmp_path: Path):
    project_root = tmp_path / "empty-project"
    project_root.mkdir()

    result = _read_project_files(project_root)
    assert result["project_context"] == ""
    assert result["project_commands"] == ""
    assert result["project_runbooks"] == ""
    assert result["project_knowledge"] == ""
    assert result["project_skills"] == ""


def test_read_project_files_with_runbooks(tmp_path: Path):
    project_root = tmp_path / "project"
    (project_root / "runbooks").mkdir(parents=True)
    (project_root / "runbooks" / "rollback.md").write_text("# Rollback\n\nRevert the deploy.\n")

    result = _read_project_files(project_root)
    assert "Rollback" in result["project_runbooks"]
    assert "Revert the deploy" in result["project_runbooks"]


def test_read_project_files_placeholder_knowledge_excluded(tmp_path: Path):
    project_root = tmp_path / "project"
    (project_root / "knowledge").mkdir(parents=True)
    (project_root / "knowledge" / "learnings.md").write_text(
        "# Learnings\n\n_No runs yet. Learnings will appear here._\n"
    )

    result = _read_project_files(project_root)
    assert result["project_knowledge"] == ""


def test_read_project_files_skill_strips_frontmatter(tmp_path: Path):
    project_root = tmp_path / "project"
    skill_dir = project_root / "skills" / "lint"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\nname: lint\nversion: 1.0\n---\n\n# Lint\n\nRun eslint .\n"
    )

    result = _read_project_files(project_root)
    assert "eslint" in result["project_skills"]
    assert "---" not in result["project_skills"]
    assert "version:" not in result["project_skills"]
